def render_with_colors(text_widget, result_text, character_colors, mode="foreground"):
    text_widget.config(state="normal")
    text_widget.delete("1.0", "end")

    for name, color in character_colors.items():
        tag_name = f"char_{name}"
        if mode == "foreground":
            text_widget.tag_config(tag_name, foreground=color, background="white")
        elif mode == "background":
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            brightness = (r*299 + g*587 + b*114) / 1000
            fg = "black" if brightness > 128 else "white"
            text_widget.tag_config(tag_name, background=color, foreground=fg)

    for line in result_text.split("\n"):
        start_index = text_widget.index("end-1c")
        text_widget.insert("end", line + "\n")
        end_index = text_widget.index("end-1c")
        for name in character_colors.keys():
            if name in line:
                tag_name = f"char_{name}"
                text_widget.tag_add(tag_name, start_index, end_index)
                text_widget.tag_raise(tag_name)
                break