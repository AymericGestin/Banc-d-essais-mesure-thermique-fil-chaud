import sys
import time
import threading
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports

class AcquisitionThread(threading.Thread):
    def __init__(self, port, baud, callback, stop_event):
        super().__init__()
        self.port = port
        self.baud = baud
        self.callback = callback
        self.stop_event = stop_event
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            # flush
            self.ser.reset_input_buffer()
            t0 = time.time()
            while not self.stop_event.is_set():
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                # expected formats: "time,temperature" or "temperature"
                parts = line.replace(';', ',').split(',')
                try:
                    if len(parts) >= 2:
                        t = float(parts[0])
                        temp = float(parts[1])
                    else:
                        temp = float(parts[0])
                        t = time.time() - t0
                    self.callback(t, temp)
                except ValueError:
                    # ignore unparsable lines
                    continue
        except Exception as e:
            print('Acquisition error:', e)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

class InterfaceFilChaud:
    def __init__(self, root):
        self.root = root
        self.root.title("Banc d'essai – Méthode du fil chaud (Tkinter)")

        main = ttk.Frame(root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Réglage des parametres physiquyes
        ttk.Label(left, text='--- Paramètres physiques ---').pack(pady=(0,4))
        self.current_var = tk.DoubleVar(value=0.5)
        ttk.Label(left, text='Courant (A)').pack()
        ttk.Entry(left, textvariable=self.current_var).pack()

        self.resistance_var = tk.DoubleVar(value=10.0)
        ttk.Label(left, text='Résistance du fil (Ω)').pack()
        ttk.Entry(left, textvariable=self.resistance_var).pack()

        self.length_var = tk.DoubleVar(value=0.1)
        ttk.Label(left, text='Longueur du fil (m)').pack()
        ttk.Entry(left, textvariable=self.length_var).pack()

        # Acquisition
        ttk.Label(left, text='--- Acquisition ---').pack(pady=(8,4))
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_var = tk.StringVar(value=ports[0] if ports else '')
        ttk.Label(left, text='Port série').pack()
        self.port_cb = ttk.Combobox(left, textvariable=self.port_var, values=ports)
        self.port_cb.pack()

        self.baud_var = tk.IntVar(value=115200)
        ttk.Label(left, text='Baudrate').pack()
        ttk.Entry(left, textvariable=self.baud_var).pack()

        self.connect_btn = ttk.Button(left, text='Connecter et Acquérir', command=self.connect_and_acquire)
        self.connect_btn.pack(pady=6)

        self.simulate_btn = ttk.Button(left, text='Simuler acquisition', command=self.simulate_acquisition)
        self.simulate_btn.pack(pady=2)

        # Fenètre de la regression linéaire
        ttk.Label(left, text='--- Régression ln(t) ---').pack(pady=(8,4))
        self.fit_start_var = tk.DoubleVar(value=0.2)
        self.fit_end_var = tk.DoubleVar(value=4.0)
        ttk.Label(left, text='Début fit (s)').pack()
        ttk.Entry(left, textvariable=self.fit_start_var).pack()
        ttk.Label(left, text='Fin fit (s)').pack()
        ttk.Entry(left, textvariable=self.fit_end_var).pack()

        ttk.Button(left, text='Calculer λ', command=self.calculate_lambda).pack(pady=6)
        ttk.Button(left, text='Exporter CSV', command=self.export_csv).pack(pady=2)

        # Figure
        fig = plt.Figure(figsize=(6,4))
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=main)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Donnée
        self.time_data = []
        self.temp_data = []
        self.acq_thread = None
        self.stop_event = threading.Event()

    def connect_and_acquire(self):
        port = self.port_var.get()
        baud = int(self.baud_var.get())
        if not port:
            messagebox.showerror('Erreur', 'Aucun port série sélectionné')
            return
        # clear previous
        self.time_data = []
        self.temp_data = []
        self.stop_event.clear()
        self.acq_thread = AcquisitionThread(port, baud, self._acq_callback, self.stop_event)
        self.acq_thread.start()
        self.connect_btn.config(text='Stopper', command=self.stop_acquisition)

    def stop_acquisition(self):
        if self.acq_thread:
            self.stop_event.set()
            self.acq_thread.join(timeout=2)
        self.connect_btn.config(text='Connecter et Acquérir', command=self.connect_and_acquire)

    def simulate_acquisition(self):
        # simulation d'une aquisition 
        duration = max(5.0, float(self.fit_end_var.get()) + 1.0)
        t = np.linspace(0.1, duration, 500)
        T = 20 + 5 * np.log(t) + np.random.normal(scale=0.05, size=t.shape)
        self.time_data = t.tolist()
        self.temp_data = T.tolist()
        self._redraw()

    def _acq_callback(self, t, temp):
        # called from acquisition thread
        self.time_data.append(t)
        self.temp_data.append(temp)
        # update plot every 0.5s
        if len(self.time_data) % 10 == 0:
            self.root.after(0, self._redraw)

    def _redraw(self):
        if not self.time_data:
            return
        t = np.array(self.time_data)
        T = np.array(self.temp_data)
        self.ax.clear()
        self.ax.plot(t, T, label='T(t)')
        self.ax.set_xlabel('Temps (s)')
        self.ax.set_ylabel('Température (°C)')
        self.ax.legend()
        self.canvas.draw()

    def calculate_lambda(self):
        if not self.time_data:
            messagebox.showerror('Erreur', 'Pas de données')
            return
        t = np.array(self.time_data)
        T = np.array(self.temp_data)
        # select fit window
        t0 = float(self.fit_start_var.get())
        t1 = float(self.fit_end_var.get())
        mask = (t >= t0) & (t <= t1)
        if mask.sum() < 10:
            messagebox.showerror('Erreur', 'Fenêtre de fit trop petite ou pas de points')
            return
        t_fit = t[mask]
        T_fit = T[mask]
        # regression de T vs ln(t)
        ln_t = np.log(t_fit)
        slope, intercept = np.polyfit(ln_t, T_fit, 1)

        # calcul des puissances q = P / L ; P = I^2 * R
        I = float(self.current_var.get())
        R = float(self.resistance_var.get())
        L = float(self.length_var.get())
        P = I**2 * R
        q = P / L
        # lambda = q / (4 * pi * slope)
        lam = q / (4.0 * np.pi * slope)

        # Affichage des résultats et du tracé aprroximé
        T_pred = slope * ln_t + intercept
        self.ax.clear()
        self.ax.plot(t, T, label='T(t)')
        self.ax.plot(t_fit, T_pred, '--', label='Fit ln(t)')
        self.ax.set_xlabel('Temps (s)')
        self.ax.set_ylabel('Température (°C)')
        self.ax.legend()
        self.canvas.draw()

        messagebox.showinfo('Résultat', f"λ = {lam:.4f} W/(m·K) \nP = {P:.4f} W, \nq = {q:.4f} W/m Pente = {slope:.6f} °C")

    def export_csv(self):
        if not self.time_data:
            messagebox.showerror('Erreur', 'Pas de données')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV Files', '*.csv')])
        if not path:
            return
        data = np.column_stack((self.time_data, self.temp_data))
        np.savetxt(path, data, delimiter=',', header='Temps,Température', comments='')
        messagebox.showinfo('Export', f'Données enregistrées: {path}')

if __name__ == '__main__':
    root = tk.Tk()
    app = InterfaceFilChaud(root)
    root.mainloop()
