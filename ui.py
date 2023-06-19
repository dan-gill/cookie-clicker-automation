from tkinter import *
from tkinter import messagebox as mb

# THEME_COLOR = "#375362"
# FONT_STYLE = ("Arial", 20, "normal")


def call(self, title, message):
    res = mb.askyesno(title=title, message=message)

    if res == 'yes':
        return "Yes"
    else:


def no_pressed():
    return "No"


class YesNoPrompt():
    def __init__(self, title, message):
        self.window = Tk()
        self.window.title(title)
        self.window.config(padx=20, pady=20, background=THEME_COLOR)

        self.message = Label(bg=THEME_COLOR, text=message)
        self.message.grid(column=1, row=0)

        self.yes_button = Button(text="Yes", highlightthickness=0, command=yes_pressed)
        self.yes_button.grid(column=0, row=1, pady=50)

        self.no_button = Button(text="No", highlightthickness=0, command=no_pressed)
        self.yes_button.grid(column=3, row=1, pady=50)

        self.window.mainloop()
