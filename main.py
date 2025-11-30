import tkinter as tk
from tkinter import scrolledtext
from controller import run_analysis, save_text
from settings import open_settings

def main():
    root = tk.Tk()
    root.title("TRPGログビューア Ver2")

    display_mode = tk.StringVar(root, value="foreground")

    output_area = scrolledtext.ScrolledText(
        root, width=100, height=40, font=("MS Gothic", 11), bg="white", fg="black"
    )
    output_area.config(tabs=("2c"))

    frame = tk.Frame(root)
    frame.pack(pady=10)

    tk.Button(frame, text="ログファイルを選んで解析",
              command=lambda: run_analysis(output_area, display_mode)).pack(side=tk.LEFT, padx=5)
    tk.Button(frame, text="設定",
              command=lambda: open_settings(root, output_area, display_mode)).pack(side=tk.LEFT, padx=5)
    tk.Button(frame, text="結果をテキスト保存",
              command=lambda: save_text(output_area)).pack(side=tk.LEFT, padx=5)

    output_area.pack(padx=10, pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()