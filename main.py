import os
import subprocess
import threading
try:
    import fcntl
except ImportError:
    fcntl = None
from typing import Any, List

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.clock import Clock

class Mode:
    LEARNING: str = "learning"
    CLASSIFICATION: str = "classification"

class MainWidget(BoxLayout):
    """
    メインウィジェットクラス。
    このウィジェットは上部にモード選択ラジオボタンを配置し、
    ドラッグ＆ドロップされたファイルやフォルダの内容を表示するスクロール可能な領域を含みます。
    UIの設定はmain.kvに定義されています。
    """
    def __init__(self, **kwargs: Any) -> None:
        """
        初期化処理。
        
        Args:
            **kwargs: 親クラスに渡す任意のキーワード引数。
        """
        super().__init__(**kwargs)
        self.mode: str = Mode.CLASSIFICATION
        self.scheduled_events: List = []
    
    def on_mode_switch(self, instance: Any) -> None:
        self.clear_items()
        if instance.text == "学習モード":
            self.mode = Mode.LEARNING
        else:
            self.mode = Mode.CLASSIFICATION
    
    def add_classification_item(self, file_path: str) -> None:
        item_box: BoxLayout = BoxLayout(
            orientation="horizontal", 
            size_hint_y=None, 
            height="130dp", 
            padding=5, 
            spacing=5
        )
        img: Image = Image(source=file_path, size_hint=(None, None), size=(0, 120))
        try:
            img.texture_update()
        except Exception:
            img.texture = None
        if img.texture and img.texture.height != 0:
            aspect_ratio: float = img.texture.width / img.texture.height
            img.width = 120 * aspect_ratio
        else:
            img.width = 120
        path_label: Label = Label(text=file_path, size_hint_x=1)
        item_box.add_widget(img)
        item_box.add_widget(path_label)
        self.ids.content_box.add_widget(item_box)
    
    def add_learning_item(self, folder_path: str) -> None:
        result_label: Label = Label(
            text=f"[{folder_path}]\n実行中...",
            size_hint_y=None,
            height="200dp",
            halign="left",
            valign="top"
        )
        result_label.bind(width=lambda instance, width: setattr(instance, 'text_size', (width, None)))
        self.ids.content_box.add_widget(result_label)
        
        def run_ls_command():
            try:
                cmd: List[str] = (["ls", "-la", folder_path] 
                                  if os.name != "nt" 
                                  else ["cmd", "/c", "dir", folder_path])
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                if fcntl:
                    flags: int = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
                    fcntl.fcntl(process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                output_lines = []
                def update_label(dt):
                    try:
                        while True:
                            line = process.stdout.readline()
                            if not line:
                                break
                            output_lines.append(line.strip())
                    except IOError:
                        pass
                    if process.poll() is None:
                        result_label.text = f"[{folder_path}]\n実行中...\n" + "\n".join(output_lines)
                        return True
                    else:
                        stdout, stderr = process.communicate()
                        if stderr:
                            result_label.text = f"[{folder_path}]\nエラー: {stderr}"
                        else:
                            for line in stdout.splitlines():
                                if line.strip() and line.strip() not in output_lines:
                                    output_lines.append(line.strip())
                            result_label.text = f"[{folder_path}]\n" + "\n".join(output_lines)
                        return False
                event = Clock.schedule_interval(update_label, 0.1)
                self.scheduled_events.append(event)
            except Exception as err:
                def show_error(dt):
                    result_label.text = f"[{folder_path}]\nエラー: {err}"
                Clock.schedule_once(show_error, 0)
        
        threading.Thread(target=run_ls_command, daemon=True).start()
    
    def clear_items(self) -> None:
        for event in self.scheduled_events:
            Clock.unschedule(event)
        self.scheduled_events.clear()
        self.ids.content_box.clear_widgets()

class MainApp(App):
    def build(self) -> MainWidget:
        self.title: str = "Kivy Cline Test"
        main_widget: MainWidget = MainWidget()
        Clock.schedule_once(lambda dt: Window.bind(on_dropfile=main_widget_on_drop), 0)
        return main_widget

def main_widget_on_drop(window: Any, file_path_bytes: bytes) -> None:
    file_path_str: str = file_path_bytes.decode("utf-8")
    app: MainApp = App.get_running_app()
    main_widget: MainWidget = app.root
    if main_widget.mode == Mode.LEARNING:
        main_widget.clear_items()
    paths = [p for p in file_path_str.splitlines() if p]
    if not paths:
        paths = [file_path_str]
    for fp in paths:
        if os.path.isdir(fp):
            if main_widget.mode == Mode.LEARNING:
                main_widget.add_learning_item(fp)
            else:
                for entry in os.listdir(fp):
                    full_path: str = os.path.join(fp, entry)
                    if os.path.isfile(full_path):
                        main_widget.add_classification_item(full_path)
        else:
            if main_widget.mode == Mode.CLASSIFICATION:
                main_widget.add_classification_item(fp)
            elif main_widget.mode == Mode.LEARNING:
                main_widget.add_learning_item(fp)

if __name__ == "__main__":
    MainApp().run()
