import os
import subprocess
import threading
import fcntl
from typing import Any, List

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock

class Mode:
    LEARNING: str = "learning"
    CLASSIFICATION: str = "classification"

class MainWidget(BoxLayout):
    """メインウィジェットクラス。

    このウィジェットは上部にモード選択ラジオボタンを配置し、
    ドラッグ＆ドロップされたファイルやフォルダの内容を表示するスクロール可能な領域を含みます。
    """

    def __init__(self, **kwargs: Any) -> None:
        """初期化処理。

        Args:
            **kwargs: 親クラスに渡す任意のキーワード引数。
        """
        super().__init__(**kwargs)
        self.mode: str = Mode.CLASSIFICATION

    # .kv ファイルで定義されたウィジェットへの参照
    learning_btn = None  # type: ToggleButton
    classify_btn = None  # type: ToggleButton
    scroll_view = None   # type: ScrollView
    content_box = None   # type: BoxLayout

    def on_mode_switch(self, instance: ToggleButton) -> None:
        """モード切替時の処理を実行する。

        Args:
            instance (ToggleButton): クリックされたトグルボタン。

        Returns:
            None
        """
        if instance.text == "学習モード":
            self.mode = Mode.LEARNING
        else:
            self.mode = Mode.CLASSIFICATION

    def add_classification_item(self, file_path: str) -> None:
        """分類モード用のアイテムを追加する。

        ドラッグ＆ドロップされたファイルに対し、画像のサムネイル（高さ120）とファイルパスを
        横並びに表示するアイテムを作成し、既存の内容の下にアペンドします。

        Args:
            file_path (str): ドラッグ＆ドロップされたファイルのパス。

        Returns:
            None
        """
        item_box: BoxLayout = BoxLayout(orientation="horizontal", size_hint_y=None, height="130dp", padding=5, spacing=5)
        img: Image = Image(source=file_path, size_hint=(None, None), size=(0, 120))
        img.texture_update()
        if img.texture:
            aspect_ratio: float = img.texture.width / img.texture.height
            img.width = 120 * aspect_ratio
        else:
            img.width = 120
        path_label: Label = Label(text=file_path, size_hint_x=1)
        item_box.add_widget(img)
        item_box.add_widget(path_label)
        self.content_box.add_widget(item_box)

    def add_learning_item(self, folder_path: str) -> None:
        """学習モード用のアイテムを追加する。

        ドラッグ＆ドロップされたフォルダのlsコマンドによる内容を、テキストとして表示します。
        lsコマンドの実行途中経過と結果を表示します。

        Args:
            folder_path (str): ドラッグ＆ドロップされたフォルダのパス。

        Returns:
            None
        """
        # Create a label to display the progress and results
        result_label: Label = Label(
            text=f"[{folder_path}]\n実行中...",
            size_hint_y=None,
            height="200dp",
            halign="left",
            valign="top"
        )
        # Bind the label's width to its text_size for proper text wrapping
        result_label.bind(width=lambda instance, width:
                         setattr(instance, 'text_size', (width, None)))
        self.content_box.add_widget(result_label)

        # Function to run the ls command and update the label
        def run_ls_command():
            try:
                # Start the ls command process
                process = subprocess.Popen(
                    ["ls", "-la", folder_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # Set stdout to non-blocking mode
                flags = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
                fcntl.fcntl(process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                # Variables to store the output
                output_lines = []

                # Function to update the label with current output
                def update_label(dt):
                    # Try to read any new output
                    try:
                        while True:
                            line = process.stdout.readline()
                            if not line:
                                break
                            output_lines.append(line.strip())
                    except IOError:
                        # No data available (non-blocking read)
                        pass

                    if process.poll() is None:
                        # Process is still running, show progress
                        result_label.text = f"[{folder_path}]\n実行中...\n" + "\n".join(output_lines)
                        return True
                    else:
                        # Process has finished, show final result
                        stdout, stderr = process.communicate()
                        if stderr:
                            result_label.text = f"[{folder_path}]\nエラー: {stderr}"
                        else:
                            # Add any remaining output
                            for line in stdout.splitlines():
                                if line.strip() and line.strip() not in output_lines:
                                    output_lines.append(line.strip())
                            result_label.text = f"[{folder_path}]\n" + "\n".join(output_lines)
                        return False

                # Schedule the label update
                Clock.schedule_interval(update_label, 0.1)

            except Exception as err:
                # Handle any exceptions
                def show_error(dt):
                    result_label.text = f"[{folder_path}]\nエラー: {err}"
                Clock.schedule_once(show_error, 0)

        # Start the ls command in a separate thread
        threading.Thread(target=run_ls_command, daemon=True).start()

    def clear_items(self) -> None:
        """現在表示されている内容をクリアする。

        Returns:
            None
        """
        self.content_box.clear_widgets()

class MainApp(App):
    """Kivyアプリケーションクラス。

    アプリケーションのエントリポイントとなるクラスです。
    """
    def build(self) -> MainWidget:
        """ウィジェットツリーを構築し、メインウィジェットを返します。

        Returns:
            MainWidget: アプリケーションのメインウィジェット。
        """
        self.title: str = "Kivy Cline Test"
        main_widget: MainWidget = MainWidget()
        Clock.schedule_once(lambda dt: Window.bind(on_dropfile=main_widget_on_drop), 0)
        return main_widget

def main_widget_on_drop(window: Any, file_path_bytes: bytes) -> None:
    """ドロップファイルイベントを処理する関数。

    ドロップされたファイルまたはフォルダのパスを取得し、現在のモードに応じた処理を行います。

    Args:
        window (Any): Kivyウィンドウオブジェクト。
        file_path_bytes (bytes): ドロップされたファイルまたはフォルダのパス（バイト列）。

    Returns:
        None
    """
    file_path: str = file_path_bytes.decode("utf-8")
    app: MainApp = App.get_running_app()
    main_widget: MainWidget = app.root

    if os.path.isdir(file_path):
        if main_widget.mode == Mode.LEARNING:
            main_widget.add_learning_item(file_path)
        else:
            for entry in os.listdir(file_path):
                full_path: str = os.path.join(file_path, entry)
                if os.path.isfile(full_path):
                    main_widget.add_classification_item(full_path)
    else:
        if main_widget.mode == Mode.CLASSIFICATION:
            main_widget.add_classification_item(file_path)
        elif main_widget.mode == Mode.LEARNING:
            # In learning mode, only directories are allowed
            label = Label(text="学習モードではディレクトリを指定してください", size_hint_y=None, height="50dp")
            main_widget.content_box.add_widget(label)

if __name__ == "__main__":
    MainApp().run()
