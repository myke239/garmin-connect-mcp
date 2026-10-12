"""Local desktop setup; credentials/consent stay in the user's terminal."""
import argparse
import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import sys
import tkinter as tk
from tkinter import ttk,messagebox
from .launching import command


def terminal(arguments):
    if os.name=='nt':
        text='& '+' '.join("'"+v.replace("'","''")+"'" for v in arguments)
        subprocess.Popen(['powershell','-NoProfile','-NoExit','-Command',text])
        return True
    for name in ('x-terminal-emulator','gnome-terminal','konsole','xterm'):
        executable=shutil.which(name)
        if executable:
            flag='--' if name=='gnome-terminal' else '-e'
            subprocess.Popen([executable,flag,*arguments]);return True
    return False


class Application:
    def __init__(self,root,auto_diagnostics=True):
        self.root=root;self.events=queue.Queue();self.tray=None
        root.title('Garmin Connect');root.geometry('740x590');root.minsize(640,500)
        frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Garmin Connect',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Local setup and phone connection. Passwords and OAuth consent stay on this computer.',wraplength=690).pack(anchor='w',pady=(4,14))
        tabs=ttk.Notebook(frame);tabs.pack(fill='both',expand=True)
        connection=ttk.Frame(tabs,padding=12);permissions=ttk.Frame(tabs,padding=12);remote=ttk.Frame(tabs,padding=12)
        tabs.add(connection,text='Connection');tabs.add(permissions,text='Permissions');tabs.add(remote,text='Phone / background')
        ttk.Label(connection,text='1. Sign in locally\n2. Verify your saved session\n3. Install the Codex plugin',justify='left').pack(anchor='w')
        self.buttons={}
        if getattr(sys,"frozen",False):
            ttk.Button(connection,text="Install this app locally",command=lambda:self.invoke(["install-local"])).pack(anchor="w",pady=4)
        for label,args in [('Sign in (private terminal)',['login']),('Verify saved session',['verify']),('Install Codex plugin',['install-plugin']),('Diagnostics',['diagnostics']),('Install FIT support',['fit-setup'])]:
            button=ttk.Button(connection,text=label,command=lambda a=args:self.invoke(a,interactive=a[0] in {'login','fit-setup'}))
            button.pack(anchor='w',pady=4);self.buttons[label]=button
        from .writes import OPERATIONS,WriteService
        service=WriteService();self.enabled=tk.BooleanVar(value=service.enabled())
        ttk.Checkbutton(permissions,text='Allow account writes (remote OAuth write scope is also required)',variable=self.enabled).pack(anchor='w')
        ttk.Label(permissions,text='Select exactly the operations you want to allow. Empty selection denies every write.').pack(anchor='w',pady=6)
        self.operations=tk.Listbox(permissions,selectmode='multiple',exportselection=False,height=8)
        self.operations.pack(fill='both',expand=True)
        current=json.loads(service.settings.load()).get('operations',list(OPERATIONS)) if service.settings.exists() else []
        for index,name in enumerate(OPERATIONS):
            self.operations.insert('end',name)
            if name in current:self.operations.selection_set(index)
        ttk.Button(permissions,text='Save local write policy',command=self.save_policy).pack(anchor='w',pady=6)
        ttk.Label(remote,text='Set up ngrok first. Start is optional; startup registration does not start now.\nYour PC must remain on for phone access.',wraplength=660).pack(anchor='w')
        for label,args in [('Set tunnel token (private terminal)',['tunnel-setup']),('Start background tunnel',['background-start']),('Stop managed tunnel',['background-stop']),('Enable startup on sign-in',['background-install']),('Disable startup',['background-uninstall'])]:
            ttk.Button(remote,text=label,command=lambda a=args:self.invoke(a,interactive=a[0]=='tunnel-setup')).pack(anchor='w',pady=3)
        ttk.Label(remote,text='OAuth approval code / ticket from ChatGPT:').pack(anchor='w',pady=(8,0))
        self.ticket=ttk.Entry(remote,width=60);self.ticket.pack(anchor='w')
        ttk.Button(remote,text='Review consent in private terminal',command=self.approve).pack(anchor='w',pady=4)
        self.output=tk.Text(frame,height=7,wrap='word',state='disabled');self.output.pack(fill='x',pady=(12,0))
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(150,self.drain)
        if auto_diagnostics:self.invoke(['diagnostics'])
    def drain(self):
        try:
            while True:self.show(self.events.get_nowait())
        except queue.Empty:pass
        self.root.after(150,self.drain)
    def show(self,text):
        self.output.configure(state='normal');self.output.delete('1.0','end');self.output.insert('end',text);self.output.configure(state='disabled')
    def invoke(self,args,interactive=False):
        arguments=command('manage',args)
        if interactive:
            if not terminal(arguments):self.show('Run this in your private terminal:\n'+shlex.join(arguments))
            else:self.show('Complete the local terminal prompt, then verify/refresh diagnostics here.')
            return
        def task():
            try:
                result=subprocess.run(arguments,capture_output=True,text=True,timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                self.events.put(result.stdout[:12000] if result.returncode==0 else 'Command failed. Use diagnostics or run the displayed launcher command locally; private exception details were omitted.')
            except Exception:self.events.put('Command failed or timed out; inspect local diagnostics.')
        threading.Thread(target=task,daemon=True).start()
    def save_policy(self):
        from .writes import WriteService
        selected=[self.operations.get(index) for index in self.operations.curselection()]
        service=WriteService();service.settings.save(json.dumps({'enabled':self.enabled.get(),'operations':selected}))
        self.show('Local write policy saved. Prepared drafts also obey the new policy at commit.');self.invoke(['diagnostics'])
    def approve(self):
        value=self.ticket.get().strip()
        if not 20<=len(value)<=100 or any(v not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for v in value):
            self.show('Paste the exact OAuth ticket from ChatGPT, not a workout draft ID.');return
        self.invoke(['approve',value],interactive=True)
    def close(self):
        if self.tray is not None:self.root.withdraw()
        else:self.root.destroy()
    def enable_tray(self):
        try:
            import pystray
            from PIL import Image,ImageDraw
            icon=Image.new('RGB',(32,32),'#163B29');ImageDraw.Draw(icon).text((9,7),'G',fill='white')
            def show(icon,item):self.root.after(0,self.root.deiconify)
            def quit_app(icon,item):icon.stop();self.root.after(0,self.root.destroy)
            self.tray=pystray.Icon('Garmin Connect',icon,'Garmin Connect',pystray.Menu(pystray.MenuItem('Open',show,default=True),pystray.MenuItem('Exit',quit_app)))
            if not self.tray.HAS_MENU:
                self.tray=None;self.show('This tray backend has no usable menu. Keep the setup window open; CLI/background features remain available.');return
            self.tray.run_detached()
        except Exception:
            self.tray=None;self.show('Tray support is unavailable on this desktop. The setup window remains usable.')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tray',action='store_true');parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    root=tk.Tk();application=Application(root,auto_diagnostics=not args.smoke_test)
    if args.smoke_test:
        root.withdraw();root.update();assert len(application.buttons)==5;root.destroy();print('PASS: desktop setup UI constructed');return
    if args.tray:application.enable_tray()
    try:root.mainloop()
    finally:
        if application.tray:application.tray.stop()


if __name__=='__main__':main()
