"""
irradiation_app.py — 2025-07-10 delimiter-fallback 版
-----------------------------------------------------
* メタ行スキップ (日時, 行検出)
* 区切り文字: Sniffer → ',' → '\t' の 3 段 fallback
"""
import sys, math, logging, csv
from pathlib import Path
import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QGroupBox,
    QToolBar, QStatusBar, QMessageBox,
)

SEARCH_KEY = "AI01C01"
CONST_C = 100.0
ISOTOPES = {"11C": 0.000566, "18F": 0.000105}

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("irradiation.log"), logging.StreamHandler()])

# ---------- CalcWorker ----------
class CalcWorker(QThread):
    finished = pyqtSignal(float, int, str)

    def __init__(self, path: Path, l_const: float):
        super().__init__()
        self.path, self.l_const = path, l_const

    # ---- main logic ----
    def run(self):
        try:
            if self.path.suffix.lower() == ".csv":
                df = self._read_csv(self.path)
            else:
                df = pd.read_excel(self.path, engine="openpyxl")

            out_total, sec = self._irradiation(df, self.l_const)
            self.finished.emit(out_total, sec, "")
        except Exception as e:
            logging.exception("計算失敗")
            self.finished.emit(0.0, 0, str(e))

    # ---- CSV 読み込み ----
    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        # 1) ヘッダ行 (「日時,」) を探す
        header_row = 0
        with open(path, "r", encoding="cp932", errors="ignore") as fh:
            for n, line in enumerate(fh):
                if line.lstrip().startswith("日時,"):
                    header_row = n
                    break

        # 2) 区切り文字推定 → fallback
        for sep_try in [None, ",", "\t"]:
            try:
                df = pd.read_csv(
                    path,
                    encoding="cp932",
                    sep=sep_try,
                    engine="python",
                    header=header_row,
                    on_bad_lines="skip",
                    skip_blank_lines=True,
                )
            except Exception:
                continue
            # AI01C01 列があれば採用
            if any(SEARCH_KEY in str(c) for c in df.columns):
                return df

        raise ValueError("区切り判定に失敗、または 'AI01C01' 列が見つかりません")

    # ---- irradiation calc ----
    @staticmethod
    def _irradiation(df: pd.DataFrame, l_const: float):
        # 列位置
        try:
            col_idx = next(i for i, c in enumerate(df.columns) if SEARCH_KEY in str(c))
        except StopIteration:
            raise ValueError(f"'{SEARCH_KEY}' 列が見つかりません")

        # 数値化
        df.iloc[:, col_idx] = pd.to_numeric(df.iloc[:, col_idx], errors="coerce")

        start_row = 0
        out_total = time_width = 0.0
        cur = start_row
        while cur < len(df):
            v = df.iat[cur, col_idx]
            if pd.isna(v):
                break
            out_total *= math.exp(-l_const * time_width)
            if v < 0.5:
                cur += 1
            else:
                break
        time_width = 1.0
        count = 0
        while cur < len(df):
            v = df.iat[cur, col_idx]
            if pd.isna(v) or v <= 0.3:
                break
            count += 1
            out_total = (
                out_total * math.exp(-l_const * time_width)
                + CONST_C * v * (1 - math.exp(-l_const * time_width))
            )
            cur += 1
        return round(out_total, 1), count

# ---------- GUI ----------
class IrradiationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照射計算アプリ")
        self.resize(640, 460)
        self.file_path: Path | None = None
        self.worker: CalcWorker | None = None

        central = QWidget(); self.setCentralWidget(central)
        v = QVBoxLayout(central); self.setStatusBar(QStatusBar())

        # toolbar
        tb = QToolBar()
        tb.addAction("開く", self._open)
        tb.addSeparator(); tb.addAction("終了", self.close)
        self.addToolBar(tb)

        # file
        g1 = QGroupBox("データファイル")
        h1 = QHBoxLayout()
        self.btn_open = QPushButton("参照…"); self.btn_open.clicked.connect(self._open)
        self.lbl_file = QLabel("<i>未選択</i>")
        h1.addWidget(self.btn_open); h1.addWidget(self.lbl_file)
        g1.setLayout(h1); v.addWidget(g1)

        # isotope
        g2 = QGroupBox("同位体"); h2 = QHBoxLayout()
        self.cmb_iso = QComboBox(); self.cmb_iso.addItems(ISOTOPES.keys())
        h2.addWidget(self.cmb_iso); g2.setLayout(h2); g2.setEnabled(False)
        self.grp_iso = g2; v.addWidget(g2)

        # run
        self.btn_run = QPushButton("計算実行"); self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run); v.addWidget(self.btn_run)

        # result
        self.lbl_res = QLabel("<h2 align='center'>ここに結果</h2>")
        self.lbl_res.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.lbl_res)

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(self, "CSV/Excel 選択", str(Path.home()),
                                           "Data (*.csv *.xlsx *.xls)")
        if p:
            self.file_path = Path(p)
            self.lbl_file.setText(self.file_path.name)
            self.grp_iso.setEnabled(True); self.btn_run.setEnabled(True)

    def _run(self):
        l_const = ISOTOPES[self.cmb_iso.currentText()]
        self.btn_run.setEnabled(False)
        self.worker = CalcWorker(self.file_path, l_const)
        self.worker.finished.connect(self._done); self.worker.start()

    def _done(self, out_total, sec, err):
        self.btn_run.setEnabled(True)
        if err:
            QMessageBox.critical(self, "エラー", err); return
        m, s = divmod(sec, 60)
        self.lbl_res.setText(f"<h2 align='center'>照射: {m}分 {s}秒<br>{out_total} mCi</h2>")

# ---------- main ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = IrradiationWindow(); win.show()
    sys.exit(app.exec())
