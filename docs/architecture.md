# Khung Griductive và hợp đồng phân công

Khung được duyệt ngày 22/11/2026. Đây là bộ kiểu dữ liệu và abstract method,
chưa có thuật toán, game chạy được hoặc kết quả benchmark.

Nguồn: `AI - Project 2.pdf` (mục 2–4) và bảng phân công nội bộ của nhóm.

## Phân công và file bàn giao

| Người phụ trách | File / đầu việc |
| --- | --- |
| Hồ Trần Quốc Thắng | `models.py`, `regions.py`: tọa độ, dữ liệu chung; `solver.py`: DPLL; `gui.py`: Pygame |
| Nguyễn Huỳnh Hải Long | `encoder.py`: VarMap, sáu loại clue, số biến và clause; phối hợp chốt models |
| Ngô Quang Minh | `evaluator.py`, `engine.py`, test đối chiếu encoder–evaluator; video |
| Nguyễn Lê Khánh Toàn | `agent/inference.py`: P1 dựng KB, P2 phân loại; report |
| Võ Tấn Lợi | Dữ liệu puzzle; `agent/runner.py`: P3; `agent/trace.py`: P4 |
| Chưa phân công | Triển khai `puzzle_io.py`, `validation.py`, `benchmark.py`; lựa chọn và triển khai ít nhất hai extension |

Thiết kế puzzle thuộc Lợi; bảng chưa chỉ rõ người viết loader nên không tự gán
phần triển khai loader cho Lợi. Không tạo abstract class cho report/video.

Các đường dẫn module trong tài liệu này tính từ `griductive/`.
Import trực tiếp từ module sở hữu, ví dụ:

```python
from griductive.models import PublicState
from griductive.solver import SATSolver
```

Lớp triển khai kế thừa ABC tương ứng và override đầy đủ abstract method.
Các tham số constructor để nối encoder/solver/validator do người triển khai
quyết định; không thay đổi chữ ký method chung nếu chưa phối hợp với bên gọi.
Không khởi tạo ABC, trả đáp án giả hoặc bắt `NotImplementedError` rồi coi là
UNKNOWN/UNSAT. Chưa cần cài Pygame khi chỉ import và kiểm tra khung.

## Quy ước dữ liệu

- Python 3.11. `Cell(row, col)` dùng chỉ số **từ 0**; GUI/JSON dùng A1, B1, C2.
  C2 tương ứng `Cell(1, 2)`. Sắp xếp Cell cho thứ tự row-major.
- Board có size nguyên dương và đúng size² nhân vật, mỗi ô đúng một nhân vật.
  Tên hiển thị duy nhất, xếp theo alphabet trong thứ tự row-major như đề yêu cầu.
  Loader kiểm tra thay vì tự đổi vị trí vì clue/solution tham chiếu tọa độ.
- Dữ liệu dùng `frozen=True`, collection dùng tuple. Các lớp chỉ là record,
  **không tự kiểm tra giá trị constructor**. Loader và các API boundary phải
  kiểm tra input; type hint không thay thế validation.
- Mỗi ô có đúng một clue, clue id duy nhất và không rỗng. Owner là ô giữ clue,
  không nhất thiết là ô được clue nói đến. Clue luôn đúng dù owner là Criminal.
- `PublicState` chỉ chứa Board, verdict công khai và clue của thẻ đã lật.
  Không chứa Puzzle, callback đọc dữ liệu bí mật, solution hay clue chưa lật.
  Verdict/clue có thứ tự row-major theo cell/owner; không trùng cell/id.
- Các vùng hợp lệ gồm row, column, neighbors 8 hướng và explicit list không lặp.
  Explicit list rỗng được chấp nhận; counting trên vùng rỗng chỉ cho k=0.
- Sáu template hiện dùng ba kiểu record: FactClue, BinaryClue, CountClue.
  Chưa thêm kiểu extension khi nhóm chưa chọn ngữ nghĩa. Khi chọn, cập nhật
  union Clue/Region, loader, encoder, evaluator, highlight và test cùng nhau.

## JSON puzzle: hợp đồng cần triển khai

Một file chứa một object, khóa bắt buộc: `id`, `size`, `characters`, `clues`,
`solution`, `initially_revealed`. Các collection JSON là array, trừ solution
là object ánh xạ tọa độ sang trạng thái. Đây là minh họa **cấu trúc trường**,
không phải puzzle hoàn chỉnh để chạy:

```json
{
  "id": "puzzle-01",
  "size": 3,
  "characters": [
    {"cell": "A1", "name": "An", "profession": "Doctor"}
  ],
  "clues": [
    {"id": "clue-a1", "owner": "A1", "type": "FACT",
     "target": "B1", "status": "INNOCENT"}
  ],
  "solution": {"A1": "CRIMINAL"},
  "initially_revealed": ["A1"]
}
```

File thực phải có đủ size² characters, clues và solution entries. Biểu diễn
clue/region còn lại:

| Loại | Trường ngoài `id`, `owner`, `type` |
| --- | --- |
| FACT | `target`, `status` |
| SAME / DIFFERENT | `left`, `right` (tọa độ) |
| EXACTLY / AT_LEAST / AT_MOST | `k` (integer), `region` |

| Region JSON | Nghĩa |
| --- | --- |
| `{"type": "ROW", "row": 2}` | Hàng 2; đổi thành index 1 |
| `{"type": "COLUMN", "column": "C"}` | Cột C; đổi thành index 2 |
| `{"type": "NEIGHBORS", "cell": "B2"}` | Hàng xóm của B2, bỏ B2 |
| `{"type": "EXPLICIT", "cells": ["A1", "C2"]}` | Danh sách ô phân biệt |

Loader từ chối khóa lạ/thiếu, bool dùng thay integer, tọa độ sai/ngoài bàn,
enum lạ, id/ô trùng, k ngoài [0, số ô vùng], solution thiếu/thừa ô, initial reveal
trùng/ngoài bàn. Tọa độ dùng chữ cột viết hoa và số hàng từ 1; không đoán/sửa dữ
liệu âm thầm. Cột theo quy ước A..Z, AA.. như bảng tính nếu cần bàn lớn hơn.
I/O lỗi dùng OSError; nội dung sai dùng ValueError có vị trí/trường gây lỗi.

## Luồng gọi và ranh giới

1. UI dùng PuzzleLoader đọc puzzle và chuyển cho Engine.load. Engine dùng
   PuzzleValidator để kiểm tra trước khi thay ván chơi, giữ puzzle riêng.
2. UI chỉ render Engine.public_state. Restart khôi phục đúng initial reveals.
3. Agent P1 truyền Board, clue đã lật và verdict công khai cho CNFEncoder.encode.
   Encoder sở hữu việc mã hóa; Agent sở hữu việc chọn thông tin public vào KB.
4. Agent P2 gọi SATSolver kiểm tra KB trước, rồi thử cả hai dấu của từng biến
   chưa biết. Trả tất cả classifications theo row-major và ghi lại mọi SAT call.
5. Hint dùng kết quả classify, lấy ô forced đầu tiên; không submit, không lật bài.
6. Runner P3 dùng public_state và Agent; chọn forced cell đầu tiên rồi gọi submit.
   Runner được gọi Engine nhưng không được đọc private fields hoặc đưa Engine
   cho Agent. Engine tự kiểm tra entailment từ KB công khai hiện tại.
7. ACCEPTED thêm verdict và clue mới atomically. Các kết quả từ chối, bao gồm
   ALREADY_REVEALED và INCONSISTENT, không đổi state và không lộ clue.
8. P4 ghi DeductionStep: số bước, active clue ids, analysis (KB và SAT queries),
   verdict, submission (judge queries và clue mới), state sau bước và status.
9. Auto Solve gọi từng step; benchmark gọi run. Một step vẫn có thể chạy lâu:
   GUI phải xử lý việc giải ngoài event loop hoặc chia nhỏ công việc để tiếp tục
   nhận sự kiện; chỉ gọi step thay run chưa đảm bảo giao diện phản hồi.
   run không tự load/restart. Không thực hiện đồng thời submit/restart/load;
   UI điều phối tuần tự, hoặc phải loại kết quả tính trên snapshot đã cũ.

Judge có thể dùng chung implementation phân loại với Agent để tránh lặp thuật
toán, nhưng chỉ truyền PublicState; không tin verdict chỉ vì khớp solution.
Nếu verdict entailed khác stored solution, báo ValueError và giữ nguyên state.
Phân loại INCONSISTENT là trạng thái cả KB, không phải nhãn một nhân vật.

Terminal analysis không submit: verdict/submission=None. Sau một bước ACCEPTED,
nếu đủ thẻ thì SOLVED; nếu chưa đủ thì RUNNING và phân loại lại ở bước kế tiếp.
Nếu Runner nhận rejection bất ngờ sau khi vừa chứng minh, dừng bằng RuntimeError
để lộ lỗi tích hợp, không lặp vô hạn. Trace.steps có thể gồm bước terminal không
lật thẻ; số deduction_steps trong benchmark chỉ đếm ACCEPTED.

## CNF, VarMap và SAT

- Literal là số nguyên khác 0; dấu dương là Criminal, dấu âm là Innocent.
- Clause là tuple literal, CNF là tuple clause. CNF rỗng là SAT; một clause
  rỗng làm CNF UNSAT. Không sửa input để thêm assumptions vĩnh viễn.
- `VarMap.primary` chứa tất cả Cell theo row-major. Primary[i] có id i+1;
  auxiliary ids nối tiếp từ N²+1. Không dùng cùng auxiliary id cho các clue
  độc lập. Tổng biến = len(primary) + auxiliary_count, số clause = len(cnf).
- `SATResult.model` là tuple (id, bool) theo id, đủ mọi biến đã khai báo khi SAT;
  khi UNSAT là None. Model rỗng `()` hợp lệ nếu không có biến và CNF là SAT.
- Stats reset theo mỗi solve: decisions đếm lần chọn giá trị cho một nhánh thử;
  propagations đếm biến mới gán bởi unit propagation; backtracks đếm lần bỏ
  một nhánh thất bại và hoàn tác assignment. runtime_s dùng đồng hồ monotonic.
- Nếu thêm pure-literal elimination, không cộng vào unit propagations; ghi rõ
  trong báo cáo cách đo để so sánh công bằng. Không đổi quy tắc đếm giữa variants.
- `SATQuery` lưu assumptions và SATResult; CNF/VarMap nằm trong result sở hữu
  query (`ClassificationResult.kb` hoặc `SubmitResult.kb`).
- Evaluator trực tiếp kiểm tra clue trên mapping Cell → Status hoàn chỉnh,
  không gọi Encoder hoặc SATSolver. Mâu thuẫn logic là False/UNSAT; dữ liệu
  sai cấu trúc là ValueError, không nhập nhằng hai trường hợp.

## Validation, benchmark và phần chưa phân công

Uniqueness dùng toàn bộ clue nhưng **không thêm solution vào KB**. Sau model đầu,
thêm blocking clause đảo các literal của biến chính để tìm assignment khác.
Khác biệt chỉ ở biến phụ không phải nghiệm game thứ hai. Kết quả là UNIQUE,
MULTIPLE hoặc UNSAT. Validation kiểm tra cả solution đã cung cấp bằng evaluator;
errors rỗng và uniqueness=UNIQUE mới hợp lệ. Nếu malformed không thể kiểm tra,
uniqueness=None. Nghiệm duy nhất không đảm bảo giải được với lịch reveal ban đầu.

Benchmark nhận factory tạo BenchmarkSystem mới cho từng case. Không tái dùng
state/stats từ case trước. Dùng cùng puzzle tuple cho mọi variant, gồm nhiều
puzzle 3×3 và 4×4; 5×5 là stress case tùy chọn.

- COMPLETED chỉ nghĩa là chạy xong: xem terminal_status để biết SOLVED/STUCK/
  INCONSISTENT. TIMEOUT và ERROR không được xóa khỏi kết quả hoặc coi là UNSAT.
- runtime_s đo vòng suy diễn gồm Agent và Judge, không gồm load/validation/
  uniqueness. Nếu lỗi trước khi vào vòng suy diễn, thời gian vòng này là 0.
- Timeout phải thực sự ngắt được vòng suy diễn đang chặn; không chỉ kiểm tra
  thời gian sau khi run trả về. Worker phải được dừng/thu hồi trước khi sang case.
  Factory top-level, có thể pickle để dùng process trên Windows/Linux.
- Đếm SAT calls và cộng decisions/propagations/backtracks của cả Agent và Judge
  đúng một lần; không tính validation/uniqueness trước khi bắt đầu vòng giải.
- primary_variables là N²; auxiliary và clauses lấy **đỉnh** qua các KB đã
  truy vấn trong vòng giải. Trace vẫn giữ KB từng bước cho số liệu chi tiết.
- Không có phép đo thì metrics=None, không giả lập toàn bộ bằng 0. Runtime là
  thời gian quan sát được của vòng suy diễn; timeout/error giữ trace nếu thu được.
- CSV gồm puzzle_id, variant, outcome, terminal_status, runtime_s, error và các
  trường metrics; giá trị chưa đo để trống. Không ghi đè file cũ âm thầm.

Benchmark dùng `GriductiveBenchmarkRunner` trong `benchmark.py`. Lệnh
`python main.py --benchmark ket-qua.csv` chạy cùng cấu hình DPLL với GUI trên
thư mục `puzzles/`. Nhánh `report` lưu số đo của lần chạy tại `report/benchmark.csv`.

## Kiểm chứng khung và tiêu chí cho implementation

Khung có test cho: không khởi tạo được ABC; type hint của abstract method giải
được; PublicState/Board/Character không chứa payload riêng và record bất biến;
Cell sắp xếp row-major. Đây không phải bằng chứng logic game đã đúng.

Khi triển khai từng phần, cần thêm test thực tương ứng:

| Phần | Trường hợp tối thiểu phải chứng minh |
| --- | --- |
| Loader/regions | Sai schema/tọa độ/id/k; góc có 3 neighbors, biên có 5, giữa có 8; explicit trùng/rỗng |
| Encoder/evaluator | Sáu template, k=0/k=size; duyệt assignment nhỏ và đối chiếu ngữ nghĩa với CNF (tồn tại assignment biến phụ) |
| DPLL | CNF rỗng, clause rỗng, chain propagation, conflict, backtrack; assumptions không rò giữa calls; model đầy đủ |
| Agent | KB UNSAT trước khi phân loại; forced/UNKNOWN; không đọc solution/clue ẩn; row-major |
| Engine | Đoán trúng nhưng chưa chứng minh vẫn bị từ chối; contradicted/unknown không đổi state; accepted lật đúng một clue; restart |
| Runner/trace | SOLVED/STUCK/INCONSISTENT, rejection bất ngờ; trace khớp SAT calls và clue trước/sau |
| Validator | Không/đúng một/nhiều nghiệm; bỏ qua khác biệt biến phụ; solution sai; unique nhưng stuck |
| Benchmark | Giữ failure/timeout, ngắt worker, thống kê không lẫn case, tổng SAT calls gồm judge, CSV không ghi đè |
| GUI | Hint không lật thẻ; hidden clue không hiện; highlight đúng ô; các nút và trạng thái từ chối rõ ràng |

Kiểm tra bằng các lệnh repo đã quy định trong README:

```bash
pre-commit run --all-files
pytest --cov=griductive --cov-report=term-missing
```

Đối với file mới chưa được Git theo dõi, chạy hook với `--files` chỉ rõ các file
đó hoặc stage chúng trước khi dùng `--all-files`. Không coi coverage của các
dataclass/ABC là coverage cho thuật toán chưa triển khai.
