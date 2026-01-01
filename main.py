import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import cv2, io, numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Импорт ваших модулей
from infrastructure import DatabaseManager, FaceRecognitionEngine
from controllers import PersonController, AccessController
from views import TextRenderer


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FaceID System Professional v10.8")
        self.root.geometry("1550x980")
        self.root.configure(bg="#f8fafc")

        self.db_manager = DatabaseManager()
        self.person_ctrl = PersonController()
        self.access_ctrl = AccessController()

        self.cap = None
        self.lockout_until = None
        self.unknown_counter = 0
        self.show_login()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.root.mainloop()

    def on_exit(self):
        self.stop_camera()
        self.root.destroy()

    def stop_camera(self):
        if self.cap: self.cap.release(); self.cap = None
        cv2.destroyAllWindows()

    def show_login(self):
        self.stop_camera()
        for w in self.root.winfo_children(): w.destroy()
        f = tk.Frame(self.root, bg="white", padx=50, pady=50, highlightthickness=1);
        f.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(f, text="Авторизация СКУД", font=("Arial", 20, "bold")).pack(pady=20)
        l_e = tk.Entry(f, width=30);
        l_e.insert(0, "admin");
        l_e.pack()
        p_e = tk.Entry(f, width=30, show="*");
        p_e.insert(0, "123");
        p_e.pack(pady=10)
        r_c = ttk.Combobox(f, values=["Администратор", "Оператор", "Руководство"], state="readonly");
        r_c.current(0);
        r_c.pack()

        def do_login():
            res = self.db_manager.conn.execute("SELECT role FROM system_users WHERE login=? AND password=? AND role=?",
                                               (l_e.get(), p_e.get(), r_c.get())).fetchone()
            if res:
                self.user = {"name": l_e.get(), "role": res[0]}
                self.show_dashboard()
            else:
                messagebox.showerror("Ошибка", "Доступ запрещен")

        tk.Button(f, text="Войти", bg="#2563eb", fg="white", command=do_login, width=20, height=2).pack(pady=20)

    def show_dashboard(self):
        for w in self.root.winfo_children(): w.destroy()
        header = tk.Frame(self.root, bg="#2563eb", height=50);
        header.pack(fill="x")
        tk.Label(header, text=f"{self.user['name']} | {self.user['role']}", fg="white", bg="#2563eb",
                 font=("Arial", 12, "bold")).pack(side="left", padx=20)
        tk.Button(header, text="Выход", command=self.show_login, bg="white").pack(side="right", padx=20)

        self.tabs = ttk.Notebook(self.root);
        self.tabs.pack(fill="both", expand=True)
        if self.user['role'] == "Администратор":
            self.ui_admin()
        elif self.user['role'] == "Оператор":
            self.ui_operator()
        else:
            self.ui_boss()

    # --- АДМИНИСТРАТОР ---
    def ui_admin(self):
        t1, t2, t3 = tk.Frame(self.tabs, bg="white"), tk.Frame(self.tabs, bg="white"), tk.Frame(self.tabs, bg="white")
        self.tabs.add(t1, text="База данных");
        self.tabs.add(t2, text="Добавить пользователя");
        self.tabs.add(t3, text="Настройки")

        # 1. Список и Редактирование
        left_f = tk.Frame(t1, bg="white");
        left_f.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        cols = ('ID', 'ФИО', 'Отдел', 'Должность', 'Уровень')
        tree = ttk.Treeview(left_f, columns=cols, show='headings')
        for c in cols: tree.heading(c, text=c)
        tree.pack(fill="both", expand=True)

        right_f = tk.Frame(t1, bg="#f8fafc", width=550);
        right_f.pack(side="right", fill="y", padx=10, pady=10)
        right_f.pack_propagate(False)

        preview = tk.Label(right_f, bg="black", width=500, height=375);
        preview.pack(pady=10)
        preview.pack_propagate(False)

        def load():
            for i in tree.get_children(): tree.delete(i)
            for r in self.db_manager.conn.execute(
                "SELECT id, name, dept, pos, level FROM persons").fetchall(): tree.insert("", "end", values=r)

        load()

        def on_click(e):
            sel = tree.selection()
            if sel:
                res = self.db_manager.conn.execute("SELECT face_img FROM biometrics WHERE person_id=?",
                                                   (tree.item(sel[0])['values'][0],)).fetchone()
                if res:
                    img = ImageTk.PhotoImage(Image.open(io.BytesIO(res[0])).resize((500, 375)))
                    preview.img_tk = img;
                    preview.configure(image=img)

        tree.bind('<<TreeviewSelect>>', on_click)

        def open_edit():
            sel = tree.selection()
            if not sel: return
            item = tree.item(sel[0])['values']
            p_id = item[0]
            win = tk.Toplevel(self.root);
            win.title("Редактировать");
            win.geometry("450x700")

            entries = []
            for lab_text, current_val in zip(["ФИО", "Отдел", "Должность"], item[1:4]):
                tk.Label(win, text=lab_text).pack(pady=5)
                e = tk.Entry(win, width=35);
                e.insert(0, current_val);
                e.pack();
                entries.append(e)

            tk.Label(win, text="Уровень доступа").pack(pady=5)
            e_l = ttk.Combobox(win, values=["Базовый", "Полный", "Спец"], state="readonly");
            e_l.set(item[4]);
            e_l.pack()

            def update_photo_logic(frame):
                if frame is None: return
                vec = self.person_ctrl.engine.extract_features(frame)
                if vec is not None:
                    _, b = cv2.imencode('.jpg', frame)
                    self.db_manager.conn.execute("UPDATE biometrics SET vector=?, face_img=? WHERE person_id=?",
                                                 (vec.tobytes(), b.tobytes(), p_id))
                    self.db_manager.conn.commit()
                    messagebox.showinfo("OK", "Фото обновлено")

            tk.Button(win, text="Загрузить новое фото", command=lambda: update_photo_logic(
                cv2.cvtColor(np.array(Image.open(filedialog.askopenfilename()).convert("RGB")),
                             cv2.COLOR_RGB2BGR))).pack(pady=10)
            tk.Button(win, text="Сфотографировать заново",
                      command=lambda: [win.withdraw(), self.cam_snap(update_photo_logic), win.deiconify()]).pack()

            tk.Button(win, text="СОХРАНИТЬ ДАННЫЕ", bg="green", fg="white", command=lambda: [
                self.db_manager.conn.execute("UPDATE persons SET name=?, dept=?, pos=?, level=? WHERE id=?",
                                             (entries[0].get(), entries[1].get(), entries[2].get(), e_l.get(), p_id)),
                self.db_manager.conn.commit(), win.destroy(), load()]).pack(pady=20)

        btn_f = tk.Frame(right_f, bg="#f8fafc")
        btn_f.pack(fill="x", pady=10)
        tk.Button(btn_f, text="Редактировать", bg="#f59e0b", fg="white", command=open_edit, width=25, height=2).pack(
            pady=5)
        tk.Button(btn_f, text="Удалить сотрудника", bg="#ef4444", fg="white", command=lambda: [
            self.db_manager.conn.execute("DELETE FROM biometrics WHERE person_id=?",
                                         (tree.item(tree.selection()[0])['values'][0],)),
            self.db_manager.conn.execute("DELETE FROM persons WHERE id=?",
                                         (tree.item(tree.selection()[0])['values'][0],)), self.db_manager.conn.commit(),
            load(), preview.configure(image='')], width=25, height=2).pack()

        # 2. Добавление
        f_reg_ui = tk.Frame(t2, bg="white", pady=30);
        f_reg_ui.pack()
        e_reg = []
        for lab in ["ФИО", "Отдел", "Должность"]:
            tk.Label(f_reg_ui, text=lab).pack();
            e = tk.Entry(f_reg_ui, width=40);
            e.pack(pady=5);
            e_reg.append(e)
        l_cb = ttk.Combobox(f_reg_ui, values=["Базовый", "Полный", "Спец"], state="readonly", width=37);
        l_cb.current(0);
        l_cb.pack(pady=10)

        def save_new(fr):
            if self.person_ctrl.add_person(str(e_reg[0].get()), str(e_reg[1].get()), str(e_reg[2].get()),
                                           str(l_cb.get()), fr):
                messagebox.showinfo("Успех", "Сотрудник добавлен в базу");
                load()

        tk.Button(t2, text="Загрузить файл (PNG/JPG)", width=35, command=lambda: save_new(
            cv2.cvtColor(np.array(Image.open(filedialog.askopenfilename()).convert("RGB")), cv2.COLOR_RGB2BGR))).pack(
            pady=5)
        tk.Button(t2, text="Сделать снимок (Пробел)", bg="#2563eb", fg="white", width=35,
                  command=lambda: self.cam_snap(save_new)).pack()

        # 3. Настройки
        tk.Label(t3, text="Порог точности распознавания (%)", font=("Arial", 12, "bold")).pack(pady=30)
        eth = tk.Entry(t3, font=("Arial", 14), justify="center");
        eth.insert(0, self.db_manager.get_setting('threshold', '85'));
        eth.pack()
        tk.Button(t3, text="Сохранить порог", bg="#2563eb", fg="white",
                  command=lambda: self.db_manager.set_setting('threshold', eth.get()) or messagebox.showinfo("OK",
                                                                                                             "Сохранено")).pack(
            pady=20)

    # --- ОПЕРАТОР ---
    def ui_operator(self):
        t1, t2 = tk.Frame(self.tabs, bg="#f8fafc"), tk.Frame(self.tabs, bg="white")
        self.tabs.add(t1, text="Мониторинг");
        self.tabs.add(t2, text="Тревоги")

        # Мониторинг - Сетка камер
        cam_grid = tk.Frame(t1, bg="#f8fafc");
        cam_grid.pack(pady=10)
        # Камера 1 (Пиксельный контейнер)
        c1_f = tk.Frame(cam_grid, width=500, height=375, bg="black");
        c1_f.grid(row=0, column=0, padx=5, pady=5);
        c1_f.pack_propagate(False)
        self.cam_v = tk.Label(c1_f, bg="black");
        self.cam_v.pack(fill="both", expand=True)

        # Камеры 2-4
        for i in range(1, 4):
            f = tk.Frame(cam_grid, width=500, height=375, bg="#1e293b");
            f.grid(row=i // 2, column=i % 2, padx=5, pady=5);
            f.pack_propagate(False)
            tk.Label(f, text=f"Камера {i + 1}\nВременно недоступна", fg="white", bg="#1e293b", font=("Arial", 10)).pack(
                expand=True)

        self.op_tree = ttk.Treeview(t1, columns=('T', 'N', 'S'), show='headings', height=5)
        for c, h in zip(('T', 'N', 'S'), ('Время', 'Сотрудник', 'Статус')): self.op_tree.heading(c, text=h)
        self.op_tree.pack(fill="x", padx=10, pady=10)

        # Тревоги
        alert_main = tk.Frame(t2, bg="white");
        alert_main.pack(fill="both", expand=True)
        tree_a = ttk.Treeview(alert_main, columns=('ID', 'T', 'C', 'M'), show='headings')
        for c, h in zip(('ID', 'T', 'C', 'M'), ('ID', 'Время', 'Камера', 'Сообщение')): tree_a.heading(c, text=h)
        tree_a.column("ID", width=50);
        tree_a.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        act_f = tk.Frame(alert_main, bg="#fef2f2", width=520);
        act_f.pack(side="right", fill="y", padx=10, pady=10)
        act_f.pack_propagate(False)
        tk.Label(act_f, text="ДЕЙСТВИЯ ОПЕРАТОРА", font=("Arial", 11, "bold"), bg="#fef2f2").pack(pady=10)

        # Окно просмотра (Пиксельный контейнер)
        inc_cont = tk.Frame(act_f, width=500, height=375, bg="gray");
        inc_cont.pack(pady=10);
        inc_cont.pack_propagate(False)
        inc_v = tk.Label(inc_cont, bg="gray");
        inc_v.pack(fill="both", expand=True)

        def show_inc(e):
            sel = tree_a.selection()
            if sel:
                r = self.db_manager.conn.execute("SELECT img FROM incidents WHERE id=?",
                                                 (tree_a.item(sel[0])['values'][0],)).fetchone()
                if r:
                    img = ImageTk.PhotoImage(Image.open(io.BytesIO(r[0])).resize((500, 375)))
                    inc_v.img_tk = img;
                    inc_v.configure(image=img)

        tree_a.bind('<<TreeviewSelect>>', show_inc)

        tk.Button(act_f, text="ВЫЗВАТЬ ОХРАНУ (ГБР)", bg="#ef4444", fg="white", width=40, height=2,
                  command=lambda: messagebox.showwarning("ВНИМАНИЕ", "Сигнал передан дежурной группе!")).pack(pady=5)
        tk.Button(act_f, text="ЭКСТРЕННАЯ БЛОКИРОВКА", bg="black", fg="white", width=40, height=2, command=lambda: [
            setattr(self, 'lockout_until',
                    datetime.now() + timedelta(minutes=int(self.db_manager.get_setting('panic_lockout', 60)))),
            messagebox.showinfo("СКУД", "Система заблокирована оператором")]).pack()

        self.run_mon(tree_a)

    def run_mon(self, t_a):
        self.stop_camera();
        self.cap = cv2.VideoCapture(0)
        thr = self.db_manager.get_setting('threshold', 85)
        max_a = int(self.db_manager.get_setting('max_attempts', 5))
        auto_lock = int(self.db_manager.get_setting('lockout', 10))

        def update():
            if not self.cap: return
            ret, frame = self.cap.read()
            if ret:
                disp = cv2.resize(frame, (500, 375));
                now = datetime.now()
                if self.lockout_until and now < self.lockout_until:
                    cv2.putText(disp, f"LOCKED {int((self.lockout_until - now).total_seconds())}s", (50, 200), 1, 2,
                                (0, 0, 255), 2)
                else:
                    name = self.access_ctrl.identify(frame, thr)
                    status = "GRANTED" if (name and name != "Unknown") else "DENIED"
                    self.db_manager.conn.execute("INSERT INTO access_log VALUES (?,?,?,?,?)",
                                                 (now, name if name else "None", status, "Cam 1", now.hour));
                    self.db_manager.conn.commit()

                    if name == "Unknown":
                        self.unknown_counter += 1
                        if self.unknown_counter >= max_a:
                            _, b = cv2.imencode('.jpg', frame)
                            cur = self.db_manager.conn.cursor();
                            cur.execute("INSERT INTO incidents (timestamp, img) VALUES (?,?)",
                                        (now.strftime("%H:%M:%S"), b.tobytes()))
                            self.db_manager.conn.commit();
                            t_a.insert("", 0, values=(cur.lastrowid, now.strftime("%H:%M"), "Cam 1", "ПРЕВЫШЕН ЛИМИТ"))
                            self.lockout_until = now + timedelta(minutes=auto_lock);
                            self.unknown_counter = 0
                    elif name and name != "Unknown":
                        self.unknown_counter = 0

                    if len(self.op_tree.get_children()) > 10: self.op_tree.delete(self.op_tree.get_children()[-1])
                    self.op_tree.insert("", 0, values=(now.strftime("%H:%M:%S"), name if name else "...", status))

                    # Отрисовка статуса на русском
                    color = (0, 255, 0) if status == "GRANTED" else (0, 0, 255)
                    text = f"{name}: доступ разрешен" if status == "GRANTED" else "Unknown: доступ запрещен"
                    disp = TextRenderer.draw(disp, text, (20, 30), color)

                img_tk = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)))
                self.cam_v.img_tk = img_tk;
                self.cam_v.configure(image=img_tk)
            self.root.after(100, update)

        update()

    def cam_snap(self, cb):
        self.stop_camera();
        c = cv2.VideoCapture(0)
        while True:
            r, f = c.read();
            cv2.imshow("Registration - SPACE to Snap", f)
            k = cv2.waitKey(1)
            if k == ord(' '): cb(f); break
            if k == 27: break
        c.release();
        cv2.destroyAllWindows()

    # --- РУКОВОДСТВО ---
    def ui_boss(self):
        t1, t2 = tk.Frame(self.tabs, bg="#f1f5f9"), tk.Frame(self.tabs, bg="white")
        self.tabs.add(t1, text="Отчеты");
        self.tabs.add(t2, text="Безопасность")

        f_f = tk.Frame(t1, bg="white", pady=10);
        f_f.pack(fill="x", padx=20)
        e_s = tk.Entry(f_f, width=12);
        e_s.insert(0, "2000-01-01");
        e_s.pack(side="left");
        e_e = tk.Entry(f_f, width=12);
        e_e.insert(0, datetime.now().strftime("%Y-%m-%d"));
        e_e.pack(side="left", padx=5)

        cards = tk.Frame(t1, bg="#f1f5f9");
        cards.pack(fill="x")
        graph = tk.Frame(t1, bg="white");
        graph.pack(fill="both", expand=True)

        def refresh():
            s, e = e_s.get(), e_e.get()
            tot = self.db_manager.conn.execute("SELECT COUNT(*) FROM access_log WHERE DATE(timestamp) BETWEEN ? AND ?",
                                               (s, e)).fetchone()[0]
            suc = self.db_manager.conn.execute(
                "SELECT COUNT(*) FROM access_log WHERE status='GRANTED' AND DATE(timestamp) BETWEEN ? AND ?",
                (s, e)).fetchone()[0]
            for w in cards.winfo_children(): w.destroy()
            for tit, val, desc in [("Всего", tot, "Проходов"), ("Успешно", suc, "Сотрудники"),
                                   ("Отказов", tot - suc, "Нарушители")]:
                f = tk.Frame(cards, bg="white", padx=30, pady=15, relief="groove");
                f.pack(side="left", padx=20, expand=True)
                tk.Label(f, text=tit, font=("Arial", 10, "bold")).pack();
                tk.Label(f, text=val, font=("Arial", 22, "bold"), fg="#2563eb").pack();
                tk.Label(f, text=desc, fg="gray").pack()

            for w in graph.winfo_children(): w.destroy()
            fig, ax = plt.subplots(figsize=(10, 3));
            h_d = {i: 0 for i in range(24)}
            for h, c in self.db_manager.conn.execute(
                "SELECT hour, COUNT(*) FROM access_log WHERE DATE(timestamp) BETWEEN ? AND ? GROUP BY hour",
                (s, e)).fetchall(): h_d[h] = c
            ax.bar(h_d.keys(), h_d.values(), color='#3b82f6');
            ax.set_title("Активность проходов по часам")
            FigureCanvasTkAgg(fig, master=graph).get_tk_widget().pack(fill="both")

        tk.Button(f_f, text="Обновить", bg="#2563eb", fg="white", command=refresh).pack(side="left", padx=10);
        refresh()

        tk.Label(t2, text="Политики безопасности", font=("Arial", 14, "bold")).pack(pady=20)
        for l, k in [("Попытки до тревоги", "max_attempts"), ("Авто-блок при тревоге (мин)", "lockout"),
                     ("Экстренный блок (мин)", "panic_lockout")]:
            tk.Label(t2, text=l).pack();
            e = tk.Entry(t2, justify="center");
            e.insert(0, self.db_manager.get_setting(k, ''));
            e.pack(pady=5)
            tk.Button(t2, text=f"Сохранить {l}",
                      command=lambda val=e, key=k: self.db_manager.set_setting(key, val.get()) or messagebox.showinfo(
                          "OK", "Настройка сохранена")).pack(pady=5)


if __name__ == "__main__":
    app = Application();
    app.run()