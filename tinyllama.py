import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sounddevice as sd
import numpy as np
import pygame
import speech_recognition as sr
import requests
import json
from PIL import Image, ImageTk 
import pyttsx3

class SpeechRecognitionApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pagnini AI")
        self.geometry("752x423")  # 7.84 inches × 4.41 inches in pixels
        self.configure(bg="#000000")

        # Initialize Pygame mixer
        pygame.mixer.init()

        # Load sound
        self.sound = pygame.mixer.Sound("sound.mp3")

        # Create a canvas for the animated dots
        self.canvas = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Create dots
        self.dot_ids = [
            self.canvas.create_oval(0, 0, 20, 20, fill="#ffffff", outline="#ffffff")
            for _ in range(3)
        ]
        self.dots_center = (376, 211)  # Center of the canvas
        self.dots_radius = 40

        # Frame for microphone controls
        self.microphone_frame = tk.Frame(self, bg="#000000")
        self.microphone_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

        # Microphone selector
        self.microphone_var = tk.StringVar()
        self.microphone_selector = ttk.OptionMenu(self.microphone_frame, self.microphone_var, "Loading...")
        self.microphone_selector.pack(side=tk.LEFT)

        # Hide button
        self.hide_button = tk.Button(self.microphone_frame, text="Hide Microphone", command=self.hide_microphone)
        self.hide_button.pack(side=tk.LEFT, padx=(10, 0))

        # Listening text
        self.listening_text = tk.Label(self, text="Listening...", fg="#ffffff", bg="#000000", font=("Helvetica", 14, "bold"))
        self.listening_text.pack(pady=(10, 0))
        self.listening_text.pack_forget()  # Initially hidden

        # Response text
        self.response_text = tk.Label(self, text="", fg="#ffffff", bg="#000000", font=("Helvetica", 12, "bold"))
        self.response_text.pack(pady=(10, 0))

        # Flags for controlling detection and response

        self.wake_word_thread = None
        self.wake_word_thread_stop_event = threading.Event()
        self.detecting = True
        self.should_hide_listening_text = False
        self.is_processing_response = False

        # Start the application
        self.update_microphone_list()
        self.update_animation()

        # Start wake-word detection
        self.tts_engine = pyttsx3.init()
        self.set_male_voice()
        self.start_wake_word_detection()

    def set_male_voice(self):
        voices = self.tts_engine.getProperty('voices')
        # Assuming the male voice is the first one, adjust index if necessary
        male_voice = next((voice for voice in voices if 'male' in voice.name.lower()), None)
        if male_voice:
            self.tts_engine.setProperty('voice', male_voice.id)
        else:
            print("Male voice not found, using default voice.")
        
        # Set the speech rate (words per minute)
        rate = self.tts_engine.getProperty('rate')  # Get the current rate
        self.tts_engine.setProperty('rate', rate - 50)  # Decrease rate for slower speech

    def speak_response(self, text):
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
        self.after(1000, self.fade_out_response_text)  # Start fading out after 1 second

    def start_recognition(self):
        def recognize():
            recognizer = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    audio = recognizer.listen(source)
                self.sound.play()
                try:
                    text = recognizer.recognize_google(audio)
                    self.response_text.config(text="You said: " + text)
                    self.listening_text.pack_forget()
                    response = self.chatbot_response(text)
                    self.response_text.config(text="Chatbot: " + response)
                    print(response)
                    self.speak_response(response)  # Speak the response
                except sr.UnknownValueError:
                    self.response_text.config(text="Sorry, I did not understand that.")
                except sr.RequestError as e:
                    self.response_text.config(text="Could not request results; {0}".format(e))
            except Exception as e:
                self.response_text.config(text=f"Error: {e}")

        threading.Thread(target=recognize).start()

    def update_animation(self):
        angle = 0
        def spin():
            nonlocal angle
            for i in range(3):
                x = self.dots_center[0] + self.dots_radius * np.cos(np.radians(angle + i * 120))
                y = self.dots_center[1] + self.dots_radius * np.sin(np.radians(angle + i * 120))
                self.canvas.coords(self.dot_ids[i], x-10, y-10, x+10, y+10)
            angle = (angle + 5) % 360
            self.after(50, spin)
        
        # Start spinning animation
        spin()

    def update_microphone_list(self):
        self.microphone_var.set("Loading...")
        try:
            # Enumerate devices
            devices = sd.query_devices()
            microphones = [d for d in devices if d['max_input_channels'] > 0]
            menu = self.microphone_selector['menu']
            menu.delete(0, 'end')
            for mic in microphones:
                menu.add_command(label=mic['name'], command=tk._setit(self.microphone_var, mic['name']))
            if microphones:
                self.microphone_var.set(microphones[0]['name'])
            else:
                self.microphone_var.set("No microphones found")
        except Exception as e:
            self.microphone_var.set("Error loading microphones")
            messagebox.showerror("Error", f"Error loading microphones: {e}")

    def start_wake_word_detection(self):
        def detect():
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source)
                print("Listening for 'Hey Friday'...")
                
                while not self.wake_word_thread_stop_event.is_set():
                    try:
                        audio = recognizer.listen(source, timeout=None)  # Set a timeout to avoid blocking
                        text = recognizer.recognize_google(audio).lower()
                        print(f"Detected text: {text}")
                        if "hey friday" in text and not self.is_processing_response:
                            print("Wake word detected!")
                            self.listening_text.pack()
                            self.sound.play()
                            self.fade_in_listening_text()
                            self.is_processing_response = True  # Prevents multiple detections
                            self.start_recognition()  # Start recognition
                            while self.response_text.cget("text") != "":
                                self.after(100)
                            self.listening_text.pack()  # Ensure listening text is visible again
                            self.is_processing_response = False  # Allow next wake word detection
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        print(f"Request error: {e}")
                    except Exception as e:
                        print(f"Unexpected error: {e}")
                    if not self.wake_word_thread_stop_event.is_set():
                        self.wake_word_thread_stop_event.wait(timeout=30)
        # Stop the old thread if it exists
        if self.wake_word_thread is not None:
            self.wake_word_thread_stop_event.set()  # Signal the thread to stop
            self.wake_word_thread.join()  # Wait for the thread to finish

        # Reset stop event and start a new thread
        self.wake_word_thread_stop_event.clear()
        self.wake_word_thread = threading.Thread(target=detect, daemon=True)
        self.wake_word_thread.start()

    def chatbot_response(self, text):
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "tinyllama",
            "prompt": text,
            "stream": False,
            "max_length": 1,
            "temperature": 0.7
        }
        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated.')
            else:
                return "Request failed with status code {}".format(response.status_code)
        except Exception as e:
            return str(e)

    def fade_in_listening_text(self):
        self.should_hide_listening_text = False
        def fade():
            current_color = self.listening_text.cget("fg")
            new_color = self._fade_color(current_color, 10)
            self.listening_text.config(fg=new_color)
            if new_color != '#ffffff':  # Continue fading until fully white
                self.after(50, fade)
            else:
                self.listening_text.after(5000, self.check_silence)  # Check silence after 5 seconds

        self.after(500, fade)

    def fade_out_response_text(self):
        def fade():
            current_color = self.response_text.cget("fg")
            new_color = self._fade_color(current_color, -10)
            self.response_text.config(fg=new_color)
            if new_color != '#000000':  # Continue fading until fully black
                self.after(50, fade)
            else:
                self.response_text.config(text="")
                # Set a flag to restart detection only after clearing the response
                self.detecting = True
                self.start_wake_word_detection()
        self.after(1000, fade)  # Start fading out 1 second after speaking

    def _fade_color(self, color, step):
        # Function to calculate the new color during fade in and out
        color = color.lstrip("#")
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = tuple(max(0, min(255, c + step)) for c in rgb)
        return "#%02x%02x%02x" % new_rgb

    def check_silence(self):
        if self.should_hide_listening_text:
            self.listening_text.pack_forget()
        else:
            self.should_hide_listening_text = True

    def hide_microphone(self):
        self.microphone_frame.pack_forget()

if __name__ == "__main__":
    app = SpeechRecognitionApp()
    app.mainloop()
