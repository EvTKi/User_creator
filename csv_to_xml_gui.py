
import customtkinter as ctk
from tkinter import filedialog, messagebox
from csv_to_xml_converter import CSVToXMLConverter
import os

class CSVToXMLApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CSV to XML Converter")
        self.geometry("800x600")
        self.converter = CSVToXMLConverter()
        
        self.setup_ui()
        
    def setup_ui(self):
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Mode selection
        self.mode_frame = ctk.CTkFrame(self)
        self.mode_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.mode_label = ctk.CTkLabel(self.mode_frame, text="Режим работы:")
        self.mode_label.pack(side="left", padx=5)
        
        self.mode_var = ctk.StringVar(value="csv")
        self.ad_mode = ctk.CTkRadioButton(
            self.mode_frame, text="Использовать AD", 
            variable=self.mode_var, value="ad"
        )
        self.ad_mode.pack(side="left", padx=5)
        
        self.csv_mode = ctk.CTkRadioButton(
            self.mode_frame, text="Использовать CSV", 
            variable=self.mode_var, value="csv"
        )
        self.csv_mode.pack(side="left", padx=5)
        
        # Domain GUID
        self.guid_frame = ctk.CTkFrame(self)
        self.guid_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.guid_label = ctk.CTkLabel(self.guid_frame, text="GUID домена:")
        self.guid_label.pack(side="left", padx=5)
        
        self.guid_entry = ctk.CTkEntry(self.guid_frame, width=300)
        self.guid_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # Directory selection
        self.dir_frame = ctk.CTkFrame(self)
        self.dir_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.dir_button = ctk.CTkButton(
            self.dir_frame, text="Выбрать папку с CSV", 
            command=self.select_directory
        )
        self.dir_button.pack(side="left", padx=5)
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, text="Не выбрано")
        self.dir_label.pack(side="left", padx=5, fill="x", expand=True)
        
        # Log output
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        # Process button
        self.process_button = ctk.CTkButton(
            self, text="Конвертировать", 
            command=self.process_files
        )
        self.process_button.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        
        # Theme switcher
        self.theme_frame = ctk.CTkFrame(self)
        self.theme_frame.grid(row=5, column=0, padx=10, pady=5, sticky="e")
        
        self.theme_label = ctk.CTkLabel(self.theme_frame, text="Тема:")
        self.theme_label.pack(side="left", padx=5)
        
        self.theme_var = ctk.StringVar(value="system")
        self.theme_menu = ctk.CTkOptionMenu(
            self.theme_frame, values=["light", "dark", "system"],
            command=self.change_theme, variable=self.theme_var
        )
        self.theme_menu.pack(side="left", padx=5)
    
    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_label.configure(text=directory)
            self.log(f"Выбрана папка: {directory}")
    
    def process_files(self):
        mode = self.mode_var.get()
        domain_guid = self.guid_entry.get()
        directory = self.dir_label.cget("text")
        
        if not directory or directory == "Не выбрано":
            messagebox.showerror("Ошибка", "Пожалуйста, выберите папку с CSV файлами")
            return
        
        if not domain_guid:
            messagebox.showerror("Ошибка", "Пожалуйста, укажите GUID домена")
            return
        
        try:
            self.log("\nНачало обработки...")
            self.converter.process(
                mode=mode,
                ad_guid=domain_guid,
                directory=directory,
                log_callback=self.log
            )
            messagebox.showinfo("Успех", "Обработка завершена успешно!")
        except Exception as e:
            self.log(f"Ошибка: {str(e)}")
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")
    
    def log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.update()
    
    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)

if __name__ == "__main__":
    app = CSVToXMLApp()
    app.mainloop()