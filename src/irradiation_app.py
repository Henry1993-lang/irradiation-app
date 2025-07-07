"""
irradiation_app.py  ― CSV(cp932) & Excel 対応 / Windows EXE 用
--------------------------------------------------------------
* CSV は Shift-JIS 前提だが、区切り文字を自動推定
* 区切り不一致行は on_bad_lines="skip" で読み飛ばし
"""

import sys, math, logging
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QGroupBox, QStatusBar,
    QToolBar, QMessageBox,
)

# ---------------- 定数 ----------------
SEARCH_KEY = "AI01C01"
CONST_C = 100.0
ISOTOPES = {"11C": 0.000566, "18F": 0.000105}

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("irradiation.log"), logging.StreamHandler()])

# ============ バックグラウンドスレッド ============
class CalcWorker(QThread):
    finished = pyqtSignal(float, int, str)  # out_total, seconds, errorMsg

    def __init__(self, path: Path, l_const: float):
        super().__init__()
        self.path = path
        self.l_const = l_const

    # ----------- 積算ロジック -----------
    @staticmethod
    def _irradiation(df: pd.DataFrame, l_const: float):
        # 1) "AI01C01" のセルを探す
        mask = df.apply(lambda col: col.astype(str).str.contains(SEARCH_KEY, na=False))
        stacked = mask.stack()
        if not stacked.any():
            raise ValueError(f"'{SEARCH_KEY}' が見つかりません")
        r_label, c_label = stacked.idxmax()
        r = int(df.index.get_loc(r_label))
        c = int(df.columns.get_loc(c_label))
        start_row = r + 1

        # 2) 列を数値化
        df.iloc[:, c] = pd.to_numeric(df.iloc[:, c], errors="coerce")

        # 3) 積算ループ
        out_total, time_width, count, cur = 0.0, 0.0, 0, start_row
        while cur < len(df):
            val = df.iat[cur, c]
            if pd.isna(val):
                break
            out_total *= math.exp(-l_const * time_width)
            if val < 0.5:
                cur += 1
            else:
                break
        time_width = 1.0
        while cur < len(df):
            val = df.iat[cur, c]
            if pd.isna(val) or val <= 0.3:
                break
            count += 1
            out_total = (
                out_total * math.exp(-l_const * time_width)
                + CONST_C * val * (1 - math.exp(-l_const * time_width))
            )
            cur += 1

        return round(out_total, 1), count

    # ----------- run() -----------
    def run(self):
        try:
            if self.path.suffix.lower() == ".csv":
                # --- 試行1: 区切り自動推定 ---
                try:
                    df = pd.read_csv(
                        self.path,
                        encoding="cp932",
                        sep=None,
                        engine="python",      # 自動Sniffer
                        on_bad_lines="skip",  # 列数不整合行を無視
                        skip_blank_lines=True,
                    )
                except Exception:
                    # --- 試行2: タブ区切りを明示 ---
                    df = pd.read_csv(
                        self.path,
                        encoding="cp932",
                        sep="\t",
                        engine="python",
                        on_bad_lines="skip",
                        skip_blank_lines=True,
                    )
            else:
                df = pd.read_excel(self.path, engine="openpyxl")

            out_total, sec = self._irradiation(df, self.l_const)
            self.finished.emit(out_total, sec, "")
        except Exception as e:
            logging.exception("計算失敗")
            self.finished.emit(0.0, 0, str(e))


# ============ メインウィンドウ ============
class IrradiationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照射計算アプリ (CSV cp932 対応)")
        self.resize(640, 460)
        self.setStyleSheet(self._dark())
        self.file_path: Path | None = None
        self.worker: CalcWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        self._build_toolbar()

        # ---- ファイル選択 ----
        grp_file = QGroupBox("データファイル選択")
        h1 = QHBoxLayout()
        self.btn_open = QPushButton("参照…")
        self.btn_open.clicked.connect(self._open_file)
        self.lbl_file = QLabel("<i>ファイル未選択</i>")
        self.lbl_file.setWordWrap(True)
        h1.addWidget(self.btn_open)
        h1.addWidget(self.lbl_file)
        grp_file.setLayout(h1)
        vbox.addWidget(grp_file)

        # ---- 同位体 ----
        grp_iso = QGroupBox("同位体")
        h2 = QHBoxLayout()
        self.cmb_iso = QComboBox()
        self.cmb_iso.addItems(ISOTOPES.keys())
        h2.addWidget(self.cmb_iso)
        grp_iso.setLayout(h2)
        grp_iso.setEnabled(False)
        self.grp_iso = grp_iso
        vbox.addWidget(grp_iso)

        # ---- 実行 ----
        self.btn_start = QPushButton("計算実行")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._run)
        vbox.addWidget(self.btn_start)

        # ---- 結果 ----
        self.lbl_result = QLabel("<h2 align='center'>ここに結果が表示されます</h2>")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.lbl_result)

        self.setStatusBar(QStatusBar())

    # ---------- UI ヘルパ ----------
    def _build_toolbar(self):
        tb = QToolBar()
        act_open = QAction("開く", self)
        act_open.triggered.connect(self._open_file)
        act_exit = QAction("終了", self)
        act_exit.triggered.connect(self.close)
        tb.addAction(act_open)
        tb.addSeparator()
        tb.addAction(act_exit)
        self.addToolBar(tb)

    @staticmethod
    def _dark():
        return (
            "QWidget{background:#2b2b2b;color:#ddd;font-size:13px;}"
            "QPushButton{background:#444;border:1px solid #666;padding:6px;border-radius:4px;}"
            "QPushButton:hover{background:#555;}"
            "QGroupBox{border:1px solid #666;margin-top:6px;}"
            "QGroupBox::title{subcontrol-origin:margin;subcontrol-position:top center;padding:0 3px;}"
        )

    # ---------- ファイル選択 ----------
    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "CSV または Excel ファイルを開く",
            str(Path.home()),
            "Data files (*.csv *.xlsx *.xls)"
        )
        if not path:
            return
        self.file_path = Path(path)
        self.lbl_file.setText(self.file_path.name)
        self.grp_iso.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.statusBar().showMessage("ファイルを選択しました", 3000)

    # ---------- 計算 ----------
    def _run(self):
        if not self.file_path:
            return
        l_const = ISOTOPES[self.cmb_iso.currentText()]
        self.btn_start.setEnabled(False)
        self.worker = CalcWorker(self.file_path, l_const)
        self.worker.finished.connect(self._done)
        self.worker.start()

    def _done(self, out_total: float, sec: int, err: str):
        self.btn_start.setEnabled(True)
        if err:
            QMessageBox.critical(self, "エラー", err)
            return
        m, s = divmod(sec, 60)
        self.lbl_result.setText(
            f"<h2 align='center'>照射時間: {m}分 {s}秒<br>{out_total} mCi</h2>"
        )
        self.statusBar().showMessage("完了", 3000)

# ============ エントリポイント ============
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = IrradiationWindow()
    win.show()
    sys.exit(app.exec())
