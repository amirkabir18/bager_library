from tkinter import *

# Define functions
def button_press(num):
    global equaltion_text
    equaltion_text += str(num)
    equation_label.set(equaltion_text)

def equals():
    global equaltion_text
    try:
        total = str(eval(equaltion_text))
        equation_label.set(total)
        equaltion_text = total
    except ZeroDivisionError:
        equation_label.set('Arithmetic Error!')
        equaltion_text = ''

def clear():
    global equaltion_text
    equation_label.set('')
    equaltion_text = ""

# Setup Display 
screen = Tk()
screen.title('GUI Calculator')
screen.geometry('500x650')

equaltion_text = ""
equation_label = StringVar()
label = Label(screen, textvariable=equation_label, font=25, bg='white', width=30, height=3)
label.pack()

# Create Frame for buttons
frame = Frame(screen)
frame.pack()

# Define buttons
buttons = [
    ('1', 0, 0), ('2', 0, 1), ('3', 0, 2), ('x', 0, 3),
    ('4', 1, 0), ('5', 1, 1), ('6', 1, 2), ('+', 1, 3),
    ('7', 2, 0), ('8', 2, 1), ('9', 2, 2), ('-', 2, 3),
    ('.', 3, 0), ('0', 3, 1), ('/', 3, 2), ('=', 3, 3)
]

for (text, row, col) in buttons:
    command = lambda x=text: button_press(x) if x != '=' else equals()
    Button(frame, text=text, font=20, width=10, height=4, command=command).grid(row=row, column=col)

clear_button = Button(screen, text='Clear', font=20, width=15, height=2, command=clear)
clear_button.pack()

screen.mainloop()