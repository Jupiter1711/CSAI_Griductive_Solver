# CSAI_Griductive_Solver

Đồ án 2 môn CSAI: xây dựng solver cho bài toán Griductive. Mã nguồn chính nằm trong package `griductive/`.

## Yêu cầu

- **Python 3.11.** Test `test_python_version` và CI đều chạy đúng phiên bản này.
- **Git.**

Kiểm tra phiên bản:

| Windows | Linux / macOS |
|---|---|
| `py -3.11 --version` | `python3.11 --version` |

## Cài đặt môi trường

Các bước dưới đây chỉ cần làm **một lần** sau khi clone repo.

### Windows (PowerShell)

```powershell
git clone https://github.com/Jupiter1711/CSAI_Griductive_Solver.git
cd CSAI_Griductive_Solver

# 1. Tạo và kích hoạt virtual environment
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Cài các công cụ dev
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. Gắn pre-commit vào git hook
pre-commit install
```

### Linux / macOS

```bash
git clone https://github.com/Jupiter1711/CSAI_Griductive_Solver.git
cd CSAI_Griductive_Solver

# 1. Tạo và kích hoạt virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Cài các công cụ dev
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. Gắn pre-commit vào git hook
pre-commit install
```

## Chạy game

```bash
pip install -r requirements.txt   # pygame, cài một lần
python main.py                    # mở danh sách puzzle trong puzzles/
python main.py --puzzle puzzles/4x4-01.json
```

Phím tắt: mũi tên chọn ô, `I`/`C` kết luận Innocent/Criminal, `H` gợi ý,
`A` tự giải, `R` chơi lại, `L` mở danh sách puzzle.

### Bộ puzzle chính thức

`puzzles/` chứa 10 màn chính thức: 3 màn 3×3, 4 màn 4×4 và 3 màn 5×5.
GUI, benchmark và CI đều lấy danh sách màn từ các file JSON trong thư mục này.
CI chạy bộ giải từ các thẻ mở ban đầu của từng màn và kiểm tra trạng thái
`SOLVED` cùng đáp án của từng ô.

`data/` lưu các phiên bản tham khảo. Bốn màn `3x3-02`, `3x3-03`, `5x5-02` và
`5x5-03` có cùng ID với bản chính thức nhưng khác danh sách thẻ mở ban đầu
(`initially_revealed`), nên bộ giải dừng ở `STUCK`. Khi tái lập số liệu báo cáo,
dùng các file trong `puzzles/`.

## Chạy benchmark

```bash
python main.py --benchmark ket-qua.csv
python main.py --benchmark mot-man.csv --puzzle puzzles/3x3-01.json --timeout 30
```

Lệnh đầu chạy lần lượt mọi file JSON trong `puzzles/` bằng DPLL và tạo một CSV mới.
Mỗi màn chạy trong một tiến trình riêng. Giới hạn mặc định là 30 giây cho khởi tạo
và 30 giây cho suy diễn. `runtime_s` chỉ đo vòng suy diễn, gồm cả Agent và Judge.
CSV lưu số biến chính, số biến phụ và mệnh đề cao nhất, tổng lượt gọi SAT,
decisions, propagations, backtracks và số lần mở thẻ thành công.
Đọc `terminal_status` để phân biệt `SOLVED` với `STUCK`. Màn lỗi hoặc quá hạn
vẫn có dòng kết quả (`ERROR` hoặc `TIMEOUT`), các số đếm chưa thu được để trống.
Chọn tên file mới cho mỗi lần đo. Nhánh `report` lưu kết quả dùng trong báo cáo
tại `report/benchmark.csv`.

## Quy trình trước khi commit

Mỗi lần mở terminal mới, nhớ **kích hoạt venv trước**:

| Windows | Linux / macOS |
|---|---|
| `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |

Sau đó, trước khi commit, chạy hai lệnh sau. Đây cũng chính là hai bước CI chạy trên GitHub:

```bash
# 1. Format và lint toàn bộ repo
pre-commit run --all-files

# 2. Chạy test kèm đo coverage
pytest --cov=griductive --cov-report=term-missing
```

Cả hai đều pass thì commit:

```bash
git add .
git commit -m "mô tả thay đổi"
git push
```

### Khi pre-commit báo `Failed`

- **Hook tự sửa file** (`trailing-whitespace`, `end-of-file-fixer`, `isort`, `black`): file đã được sửa sẵn, bạn chỉ cần `git add` lại các file đó rồi commit lần nữa.
- **`flake8` báo lỗi:** flake8 không tự sửa được. Đọc thông báo (dạng `file.py:dòng:cột: mã lỗi`), sửa tay, rồi chạy lại.

Vì đã chạy `pre-commit install`, mỗi lần `git commit` hook sẽ tự chạy trên các file đã stage. Bạn không cần đợi đến CI mới thấy lỗi.
