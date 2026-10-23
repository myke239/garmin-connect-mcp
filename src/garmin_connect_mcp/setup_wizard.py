"""Page-based local setup; credentials and owner consent never need a terminal."""
import argparse
import queue
from pathlib import Path
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from . import __version__
from .setup_service import Backend, SetupError, login


PAGES = {
    'welcome': ('Install Garmin Connect', 'Connect your Garmin account to ChatGPT or Codex. Setup will guide you through each step.'),
    'signin': ('Connect your Garmin account', 'Your password is used only to sign in to Garmin. Have your Garmin email, password and verification code ready.'),
    'mfa': ('Enter your verification code', 'Use the code Garmin sent you. This code is used only to finish signing in.'),
    'client': ('Where will you use Garmin?', 'Choose the app you want to connect.'),
    'codex': ('Connect Codex', 'Setup will install the Garmin plugin and check its tools. If needed, it downloads and verifies the official Codex helper automatically.'),
    'hosting': ('Set up your ChatGPT connection', 'Do you already use an HTTPS address for another MCP connector?'),
    'existing': ('Use your existing HTTPS address', 'Keep your shared gateway running. Setup will check Garmin at this address without starting another tunnel.'),
    'ngrok': ('Connect with ngrok', 'Copy your authtoken from your ngrok account and paste it below. Your PC must stay awake for ChatGPT access.'),
    'chatgpt': ('Add Garmin in ChatGPT', 'In Plugins, choose Add custom MCP server. Enter the details below and start the connection.'),
    'request': ('Review your connection request', 'Start connecting Garmin in ChatGPT. Copy the connection code from the browser approval page and paste it here.'),
    'review': ('Approve your connection', 'Approve only the ChatGPT connection you just started. Local write settings still apply.'),
    'confirm': ('Finish connecting in ChatGPT', 'Return to the browser, choose Continue, then create and install the plugin. Come back here to verify it.'),
    'finish': ('You\u2019re connected', 'Garmin sign-in and the installed tools passed verification. Open a new chat and try: Summarize my last three activities.'),
}


class Application:
    def __init__(self, root, auto_diagnostics=True, backend=None, installed=False):
        self.root = root
        self.backend = backend or Backend()
        self.events = queue.Queue()
        self.cancelled = threading.Event()
        self.mfa_waiter = None
        self.busy = False
        self.history = []
        self.page = ''
        self.force_signin = False
        self.client = tk.StringVar(value='chatgpt')
        self.origin = tk.StringVar(value=self.backend.existing_origin())
        self.hosting = tk.StringVar(value='existing' if self.origin.get() else 'new')
        self.url = ''
        root.title('Garmin Connect Setup')
        root.geometry('760x560')
        root.minsize(700, 520)
        if os.name == 'nt':
            resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2] / 'assets'))
            icon = resources / 'branding/das-kreb-logo.ico'
            if icon.is_file():
                root.iconbitmap(str(icon))
        style = ttk.Style(root)
        style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'))
        style.configure('Body.TLabel', font=('Segoe UI', 11))
        style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), padding=(20, 10))
        outer = ttk.Frame(root, padding=28)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='GARMIN CONNECT', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.step = ttk.Label(outer, foreground='#526278')
        self.step.pack(anchor='w', pady=(8, 16))
        self.title = ttk.Label(outer, style='Title.TLabel', wraplength=680)
        self.title.pack(anchor='w')
        self.description = ttk.Label(outer, style='Body.TLabel', wraplength=680, justify='left')
        self.description.pack(anchor='w', pady=(12, 18))
        self.content = ttk.Frame(outer)
        self.content.pack(fill='both', expand=True)
        self.message = ttk.Label(outer, foreground='#ad2634', wraplength=680)
        self.message.pack(anchor='w', pady=(8, 12))
        self.progress = ttk.Progressbar(outer, mode='indeterminate')
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', side='bottom')
        self.back = ttk.Button(buttons, text='Back', command=self.go_back)
        self.back.pack(side='left')
        self.primary = ttk.Button(buttons, style='Primary.TButton')
        self.primary.pack(side='right')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Return>', lambda event: self.primary.invoke())
        root.after(80, self.drain)
        self.show_page('signin' if installed else 'welcome', remember=False)

    def field(self, label, secret=False, variable=None, readonly=False):
        ttk.Label(self.content, text=label, style='Body.TLabel').pack(anchor='w', pady=(6, 4))
        entry = ttk.Entry(self.content, width=68, show='\u2022' if secret else '', textvariable=variable)
        entry.pack(fill='x', pady=(0, 10))
        if readonly:
            entry.configure(state='readonly')
        return entry

    def button(self, label, action):
        self.primary.configure(text=label, command=action, state='normal')

    def show_page(self, page, remember=True):
        if remember and self.page and page != self.page:
            self.history.append(self.page)
        self.page = page
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        for child in self.content.winfo_children():
            child.destroy()
        self.message.configure(text='')
        self.back.configure(state='normal' if self.history and page not in {'mfa', 'confirm', 'finish'} else 'disabled')
        title, text = PAGES[page]
        self.title.configure(text=title)
        self.description.configure(text=text)
        self.step.configure(text='Setup / ' + __version__ if page == 'welcome' else 'Garmin setup / ' + title)
        self.render(page)

    def render(self, page):
        if page == 'welcome':
            self.button('Begin Install', lambda: self.task(self.backend.install, lambda value: self.show_page('signin')))
        elif page == 'signin':
            if self.backend.session_saved() and not self.force_signin:
                ttk.Label(self.content, text='A saved Garmin session was found.', style='Body.TLabel').pack(anchor='w')
                ttk.Button(self.content, text='Use a different Garmin sign-in', command=self.new_signin).pack(anchor='w', pady=16)
                self.button('Verify Garmin', lambda: self.task(self.backend.verify, lambda value: self.show_page('client')))
            else:
                self.signin_fields()
        elif page == 'mfa':
            self.code = self.field('Verification code', secret=True)
            self.code.focus_set()
            self.button('Next', self.submit_mfa)
        elif page in {'client', 'hosting'}:
            options = [('ChatGPT (including phone access)', 'chatgpt'), ('Codex', 'codex')] if page == 'client' else [('Set up a new ngrok connection', 'new'), ('Use my existing HTTPS address', 'existing')]
            variable = self.client if page == 'client' else self.hosting
            for label, value in options:
                ttk.Radiobutton(self.content, text=label, value=value, variable=variable).pack(anchor='w', pady=12)
            def next_page():
                target = ('codex' if self.client.get() == 'codex' else 'hosting') if page == 'client' else ('existing' if self.hosting.get() == 'existing' else 'ngrok')
                self.show_page(target)
            self.button('Next', next_page)
        elif page == 'codex':
            self.button('Connect Codex', lambda: self.task(self.backend.connect_codex, lambda value: self.show_page('finish')))
        elif page == 'existing':
            self.field('HTTPS address, for example https://your-host.ngrok-free.dev', variable=self.origin)
            self.button('Check connection', self.check_existing)
        elif page == 'ngrok':
            if os.name == 'nt':
                ttk.Label(self.content, text='This connection starts automatically when you sign in to Windows.', style='Body.TLabel', wraplength=660).pack(anchor='w', pady=(0, 8))
            ttk.Button(self.content, text='Open ngrok authtoken page', command=lambda: webbrowser.open('https://dashboard.ngrok.com/get-started/your-authtoken')).pack(anchor='w', pady=(0, 10))
            self.token = self.field('Ngrok authtoken (leave blank to keep a saved token)', secret=True)
            self.button('Save and connect', self.connect_ngrok)
        elif page == 'chatgpt':
            ttk.Label(self.content, text='Name: Garmin Connect\nAuthentication: OAuth / Dynamic Client Registration', style='Body.TLabel').pack(anchor='w', pady=(0, 8))
            self.field('Server URL', variable=tk.StringVar(value=self.url), readonly=True)
            self.button('Copy URL and open ChatGPT', self.open_chatgpt)
        elif page == 'request':
            self.ticket = self.field('Connection code from the browser')
            self.button('Review request', self.review_request)
        elif page == 'review':
            review = self.backend.review
            access = 'Read and modify Garmin records' if 'garmin:write' in review['scopes'] else 'Read Garmin records'
            ttk.Label(self.content, text=access, font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 12))
            ttk.Label(self.content, text='Server: ' + review['resource'] + '\nCallback: ' + review['callback'] + '\nClient: ' + review['client_id'], wraplength=660).pack(anchor='w')
            self.button('Approve connection', lambda: self.task(self.backend.approve, lambda value: self.show_page('confirm')))
        elif page == 'confirm':
            self.button('Verify connection', lambda: self.task(self.backend.verify_chatgpt, lambda value: self.show_page('finish')))
        elif page == 'finish':
            ttk.Label(self.content, text='\u2713 Garmin account verified\n\u2713 58 installed tools verified\n\u2713 ' + ('ChatGPT connection verified' if self.client.get() == 'chatgpt' else 'Codex plugin installed'), style='Body.TLabel').pack(anchor='w', pady=8)
            self.button('Close', self.close)
            ttk.Button(self.content, text='Account permissions', command=self.permissions).pack(anchor='w', pady=18)

    def signin_fields(self):
        self.email = self.field('Garmin email')
        self.password = self.field('Garmin password', secret=True)
        self.button('Sign in', self.sign_in)

    def new_signin(self):
        self.force_signin = True
        for child in self.content.winfo_children():
            child.destroy()
        self.signin_fields()

    def sign_in(self):
        email, password = self.email.get(), self.password.get()
        if not email.strip() or not password:
            self.message.configure(text='Enter your Garmin email and password.')
            return
        self.email.delete(0, 'end')
        self.password.delete(0, 'end')
        self.task(lambda: login(email, password, self.prompt_mfa, self.cancelled.is_set), lambda value: self.show_page('client'))

    def review_request(self):
        ticket = self.ticket.get().strip()
        self.task(lambda: self.backend.find_request(ticket), lambda value: self.show_page('review'))

    def prompt_mfa(self):
        event, answer = threading.Event(), []
        self.events.put(('mfa', (event, answer)))
        for _ in range(1800):
            if self.cancelled.is_set():
                raise SetupError('Sign-in cancelled.')
            if event.wait(.1):
                return answer[0]
        raise SetupError('The verification code timed out. Sign in again.')

    def submit_mfa(self):
        value = self.code.get().strip()
        if not value:
            self.message.configure(text='Enter your verification code.')
            return
        self.code.delete(0, 'end')
        event, answer = self.mfa_waiter
        answer.append(value)
        self.mfa_waiter = None
        self.primary.configure(state='disabled')
        self.busy = True
        event.set()

    def connect_ngrok(self):
        token = self.token.get().strip()
        self.token.delete(0, 'end')
        self.task(lambda: self.backend.start_tunnel(token), self.server_ready)

    def check_existing(self):
        value = self.origin.get()
        self.task(lambda: self.backend.check_server(value), self.server_ready)

    def server_ready(self, url):
        self.url = url
        self.show_page('chatgpt')

    def open_chatgpt(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url)
        webbrowser.open('https://chatgpt.com/plugins')
        self.show_page('request')

    def task(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.message.configure(text='Working\u2026')
        self.primary.configure(state='disabled')
        self.back.configure(state='disabled')
        self.progress.pack(fill='x', before=self.primary.master, pady=(0, 10))
        self.progress.start()
        def run():
            try:
                self.events.put(('done', (done, work())))
            except SetupError as error:
                self.events.put(('error', str(error)))
            except Exception:
                self.events.put(('error', 'This step could not finish. Check your connection, then try again.'))
        threading.Thread(target=run, daemon=True).start()

    def drain(self):
        if self.cancelled.is_set():
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'mfa':
                    self.mfa_waiter = value
                    self.show_page('mfa', remember=False)
                elif kind == 'done':
                    self.busy = False
                    callback, result = value
                    callback(result)
                else:
                    self.show_page('signin' if self.page == 'mfa' else self.page, remember=False)
                    self.message.configure(text=value)
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

    def go_back(self):
        if not self.busy and self.history:
            self.show_page(self.history.pop(), remember=False)

    def close(self):
        self.cancelled.set()
        self.root.destroy()

    def permissions(self):
        import json
        from .writes import WriteService, OPERATIONS
        service = WriteService()
        dialog = tk.Toplevel(self.root)
        dialog.title('Account permissions')
        frame = ttk.Frame(dialog, padding=22)
        frame.pack(fill='both', expand=True)
        enabled = tk.BooleanVar(value=service.enabled())
        ttk.Checkbutton(frame, text='Allow reviewed account writes', variable=enabled).pack(anchor='w')
        choices = tk.Listbox(frame, selectmode='multiple', exportselection=False, height=14, width=55)
        choices.pack(fill='both', expand=True, pady=12)
        current = json.loads(service.settings.load()).get('operations', list(OPERATIONS)) if service.settings.exists() else list(OPERATIONS)
        for index, name in enumerate(OPERATIONS):
            choices.insert('end', name)
            if name in current:
                choices.selection_set(index)
        def save():
            service.settings.save(json.dumps({'enabled': enabled.get(), 'operations': [choices.get(i) for i in choices.curselection()]}))
            dialog.destroy()
        ttk.Button(frame, text='Save', command=save).pack(anchor='e')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tray', action='store_true')
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--installed', action='store_true')
    args = parser.parse_args()
    root = tk.Tk()
    backend = None
    if args.smoke_test:
        from types import SimpleNamespace
        backend = SimpleNamespace(existing_origin=lambda: '', session_saved=lambda: False,
            review={'resource': 'https://example.invalid/mcp/garmin-connect/',
                'client_id': 'synthetic-client', 'callback': 'https://chatgpt.com/oauth/callback',
                'scopes': ['garmin:read']})
    app = Application(root, backend=backend, installed=args.installed)
    if args.smoke_test:
        root.withdraw()
        root.update()
        assert app.page == 'welcome' and app.primary['text'] == 'Begin Install'
        assert str(app.back['state']) == 'disabled'
        for page in PAGES:
            app.show_page(page)
            root.update_idletasks()
            assert app.primary['text'] and str(app.primary['state']) == 'normal'
            assert app.primary.winfo_y() + app.primary.winfo_height() <= app.primary.master.winfo_height()
        root.destroy()
        print('PASS: all guided setup pages constructed with one primary action')
        return
    root.mainloop()


if __name__ == '__main__':
    main()
