import tkinter as tk
import os
from controller import run_analysis, export_formatted_html
from settings import open_settings

def main():
    root = tk.Tk()
    root.title("TRPGログビューア Ver2")
    root.geometry("800x120")

    # Control panel (top frame)
    control_frame = tk.Frame(root)
    control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

    # File selection and color/settings/export
    def on_analyze_clicked():
        run_analysis()
        update_file_label()

    tk.Button(control_frame, text="ログファイルを選んで解析",
              command=on_analyze_clicked).pack(side=tk.LEFT, padx=5)

    tk.Button(control_frame, text="色・設定",
              command=lambda: open_settings(root)).pack(side=tk.LEFT, padx=5)

    tk.Button(control_frame, text="整形済みHTMLを保存",
              command=export_formatted_html).pack(side=tk.LEFT, padx=5)

    # File path display label
    file_label = tk.Label(root, text="ファイル: 未選択", fg="#666", justify=tk.LEFT)
    file_label.pack(side=tk.TOP, fill=tk.X, padx=10, pady=2)

    def update_file_label():
        import controller
        if controller.last_file_path:
            filename = os.path.basename(controller.last_file_path)
            file_label.config(text=f"ファイル: {filename}", font=("Arial", 11, "bold"))
        else:
            file_label.config(text="ファイル: 未選択")

    root.mainloop()

if __name__ == "__main__":
    main()
