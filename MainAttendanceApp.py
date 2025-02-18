import cv2
import face_recognition
import numpy as np
import mysql.connector
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

# Global variables
camera_running = False
cap = None
db = None
cursor = None
student_info = []
last_marked_time = {}  # Store student information as (student_id, student_name, face_image_path)

# Function to toggle camera
def toggle_camera():
    global camera_running, cap
    if camera_running:
        stop_camera()
    else:
        start_camera()

# Function to start the camera
def start_camera():
    global camera_running, cap
    if camera_running:
        return
    cap = cv2.VideoCapture(0)
    camera_running = True
    camera_button.config(text="Stop Camera")
    main_loop()

# Function to stop the camera
def stop_camera():
    global camera_running, cap
    if not camera_running:
        return
    cap.release()
    cv2.destroyAllWindows()
    camera_running = False
    camera_button.config(text="Start Camera")

# Main loop for camera and face recognition
def main_loop():
    global db, cursor
    db, cursor = connect_to_database()
    known_face_encodings, student_ids, student_names = initialize_known_faces_from_db()  # Initialize from DB
    while camera_running:
        ret, frame = cap.read()
        if not ret:
            break
        face_locations = face_recognition.face_locations(frame)
        for face_location in face_locations:
            process_face(frame, face_location, known_face_encodings, student_ids, student_names)
        cv2.imshow('Video', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop_camera()
    cleanup()

# Function to process a detected face
def process_face(frame, face_location, known_face_encodings, student_ids, student_names):
    face_encoding = face_recognition.face_encodings(frame, [face_location])[0]
    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
    if True in matches:
        student_id = student_ids[matches.index(True)]
        student_name = student_names[matches.index(True)]
        mark_attendance(student_id, student_name)  # Updated to include student_name
        message = "Identified: Student ID {} - {}".format(student_id, student_name)
        color = (0, 255, 0)  # Green for identified
    else:
        message = "Unidentified"
        color = (0, 0, 255)  # Red for unidentified
    top, right, bottom, left = face_location
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    cv2.putText(frame, message, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

# Function to clean up resources
def cleanup():
    global db, cursor
    if db:
        db.commit()
        cursor.close()
        db.close()

# Function to connect to the database
def connect_to_database():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="faces"
    )
    cursor = db.cursor()
    return db, cursor

# Function to initialize known faces from the database
def initialize_known_faces_from_db():
    known_face_encodings = []
    student_ids = []
    student_names = []
    
    db, cursor = connect_to_database()
    cursor.execute("SELECT id, name, facepath FROM student_details")
    rows = cursor.fetchall()
    for row in rows:
        student_id, student_name, face_image_path = row
        image = face_recognition.load_image_file(face_image_path)
        known_face_encodings.append(face_recognition.face_encodings(image)[0])
        student_ids.append(student_id)
        student_names.append(student_name)
    
    cursor.close()
    db.close()
    return known_face_encodings, student_ids, student_names

# Function to mark attendance in the database
def mark_attendance(student_id, student_name):
    cooldown_period = timedelta(hours=1)  # Set the cooldown period to 1 hour
    current_time = datetime.now()

    if student_id in last_marked_time:
        last_time = last_marked_time[student_id]
        time_elapsed = current_time - last_time

        if time_elapsed < cooldown_period:
            remaining_time = cooldown_period - time_elapsed
            remaining_time_str = str(remaining_time).split('.')[0]  # Get the remaining time as a string
            message = f"Your attendance has already been marked.\nTry again after {remaining_time_str}."
            messagebox.showinfo("Cooldown", message)
            return  # Do not mark attendance

    # If cooldown period has passed or this is the first time marking attendance
    last_marked_time[student_id] = current_time  # Update the last marked time
    insert_query = "INSERT INTO attendance (student_id, student_name, attendance_time) VALUES (%s, %s, %s)"
    cursor.execute(insert_query, (student_id, student_name, current_time))
    db.commit()
    print(f"Marked attendance for {student_name}.")

def insert_student_details(student_id, student_name, face_image_path):
    db, cursor = connect_to_database()  # Connect to the database
    insert_query = "INSERT INTO student_details (id, name, facepath) VALUES (%s, %s, %s)"
    cursor.execute(insert_query, (student_id, student_name, face_image_path))
    db.commit()
    cursor.close()
    db.close()

# Function to open the Add Student window
def add_student():
    student_id = student_id_entry.get()
    student_name = student_name_entry.get()
    face_image_path = face_image_path_entry.get()
    if student_id and student_name and face_image_path:
        student_info.append((student_id, student_name, face_image_path))
        insert_student_details(student_id, student_name, face_image_path)
        student_id_entry.delete(0, tk.END)
        student_name_entry.delete(0, tk.END)
        face_image_path_entry.delete(0, tk.END)
        messagebox.showinfo("Success", "Student added successfully.")
    else:
        messagebox.showerror("Error", "Please fill in all fields.")

# ... (previous code) ...

# Function to open a new window and show student details
def display_student_details():
    def delete_student():
        # Retrieve the selected item
        selected_item = student_details_table.selection()
        if selected_item:
            # Get the values from the selected item
            values = student_details_table.item(selected_item, 'values')
            student_id = values[0]

            # Open a connection to the database and delete the student
            db, cursor = connect_to_database()
            delete_query = "DELETE FROM student_details WHERE id = %s"
            cursor.execute(delete_query, (student_id,))
            db.commit()
            cursor.close()
            db.close()

            # Remove the item from the Treeview
            student_details_table.delete(selected_item)

    student_details_window = tk.Toplevel()
    student_details_window.title("Student Details")

    # Create the Treeview widget
    student_details_table = ttk.Treeview(student_details_window, columns=("ID", "Name", "Face Image Path"))
    student_details_table.heading("#1", text="ID")
    student_details_table.heading("#2", text="Name")
    student_details_table.heading("#3", text="Face Image Path")

    # Populate the Treeview widget with data from the student_details table
    db, cursor = connect_to_database()
    cursor.execute("SELECT student_id, student_name, attendance_time FROM attendance")
    rows = cursor.fetchall()
    for row in rows:
        student_details_table.insert("", "end", values=row)

    cursor.close()
    db.close()

    student_details_table.pack()

    # Add a Delete button
    delete_button = ttk.Button(student_details_window, text="Delete", style="DarkTheme.TButton", command=delete_student)
    delete_button.pack()

    student_details_table.bind("<Double-1>", lambda event: delete_student())

    student_details_window.mainloop()



# Function to exit the application
def exit_application():
    stop_camera()
    root.destroy()

# Create the main window
root = tk.Tk()
root.title("Face Recognition Attendance System")

# Configure the dark theme style
style = ttk.Style()
style.configure("DarkTheme.TButton", foreground="black", background="gray")
style.configure("DarkTheme.TLabel", foreground="black", background="gray")
style.map("DarkTheme.TButton", foreground=[("active", "white")])

# Set the window size and background color
root.geometry("400x400")
root.configure(bg="#808080")

# Create a frame for button organization
frame = tk.Frame(root, background="black")
frame.pack(pady=20)

# Add buttons for controlling the camera
camera_button = ttk.Button(frame, text="Start Camera", style="DarkTheme.TButton", command=toggle_camera)
camera_button.grid(row=0, column=0, padx=10, pady=10)

add_student_button = ttk.Button(frame, text="Add Student", style="DarkTheme.TButton", command=add_student)
add_student_button.grid(row=0, column=1, padx=10, pady=10)

exit_button = ttk.Button(frame, text="Exit", style="DarkTheme.TButton", command=exit_application)
exit_button.grid(row=0, column=2, padx=10, pady=10)

# Create input fields for adding a new student
student_id_label = ttk.Label(root, text="Student ID", style="DarkTheme.TLabel")
student_id_label.pack()
student_id_entry = ttk.Entry(root)
student_id_entry.pack()

student_name_label = ttk.Label(root, text="Student Name", style="DarkTheme.TLabel")
student_name_label.pack()
student_name_entry = ttk.Entry(root)
student_name_entry.pack()

face_image_path_label = ttk.Label(root, text="Face Image Path", style="DarkTheme.TLabel")
face_image_path_label.pack()
face_image_path_entry = ttk.Entry(root)
face_image_path_entry.pack()

show_student_details_button = ttk.Button(frame, text="Show Student Attendance", style="DarkTheme.TButton", command=display_student_details)
show_student_details_button.grid(row=0, column=3, padx=10, pady=10)




# Run the GUI
root.mainloop()