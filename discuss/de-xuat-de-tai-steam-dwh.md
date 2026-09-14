# ĐỀ XUẤT ĐỀ TÀI CUỐI KỲ

## Tên đề tài

**Xây dựng kho dữ liệu và khai phá dữ liệu thị trường game trên nền tảng Steam**

---

## Mô tả

Steam có hơn 100.000 sản phẩm và mỗi ngày thêm hàng chục game mới. Dữ liệu về giá, lượng người chơi, thể loại và đánh giá đều công khai, nhưng phân tán, không có lịch sử, và không truy vấn đa chiều được.

Đề tài thu thập dữ liệu thật từ các API của Steam theo lịch tự động, nạp vào kho dữ liệu thiết kế theo lược đồ hình sao, rồi khai phá để trả lời những câu hỏi mà nhà phát triển game phải quyết định trước khi phát hành: đặt giá bao nhiêu, chọn tổ hợp thể loại nào, phát hành vào lúc nào.

Phạm vi: khoảng 5.000 game phổ biến nhất, theo dõi liên tục trong suốt thời gian làm đồ án.

**Đáp ứng 4 tiêu chí dữ liệu**

- **Đúng** — toàn bộ từ API chính thức của Valve, mỗi bản ghi có thời điểm thu thập thật, không sinh dữ liệu giả.
- **Đủ** — 5.000 game × nhiều mốc đo mỗi ngày cho hàng triệu bản ghi sự kiện; chiều dữ liệu gồm game, thể loại, tag người chơi, nhà phát hành, ngày và giờ.
- **Sạch** — dữ liệu thô có rác thật: HTML lẫn trong mô tả, chuỗi ngày không nhất quán, khoảng người sở hữu ở dạng văn bản, trường giá khuyết ở game miễn phí. Hệ thống có tầng tiền xử lý riêng để xử lý.
- **Sống** — lượng người chơi đổi theo từng giờ, giá đổi theo đợt sale. Pipeline chạy theo lịch, dữ liệu tích lũy không cần can thiệp tay.

---

## Tính năng

**1. Pipeline thu thập tự động**

Bốn luồng chạy độc lập theo tần suất khác nhau: lượng người chơi theo giờ, metadata và tag theo tuần, bài đánh giá theo ngày. Dữ liệu thô được lưu nguyên bản vào data lake trước khi biến đổi, để tái xử lý được khi phát hiện lỗi logic mà không phải thu thập lại.

Do API có giới hạn số lượt gọi mỗi ngày, hệ thống lấy mẫu phân tầng: game phổ biến đo dày, game ít phổ biến đo thưa, và giờ đo được rải đều trong ngày để không bị lệch về một khung giờ.

**2. Kho dữ liệu đa chiều**

Lược đồ hình sao với hai mức hạt: bảng sự kiện chi tiết theo giờ cho phân tích trong ngày, và bảng tổng hợp theo ngày cho phân tích dài hạn. Quan hệ game–tag và game–thể loại là nhiều-nhiều nên có bảng cầu riêng. Chiều thời gian hai cấp (ngày và giờ) để phân tích được cả theo mùa và theo khung giờ.

Hỗ trợ đầy đủ các phép truy vấn đa chiều: tổng hợp lên, khoan xuống, cắt lát, cắt khối, xoay trục.

**3. Khai phá dữ liệu**

- Luật kết hợp trên tập tag của mỗi game, tìm tổ hợp thể loại thường đi cùng nhau và tổ hợp nào gắn với đánh giá tích cực cao.
- Phân cụm để phân tầng thị trường theo lượng người chơi, giá, tỷ lệ đánh giá tích cực và thời lượng chơi.
- Cây quyết định dự đoán game có thuộc nhóm hiệu suất cao trong thể loại của nó, sinh ra luật dạng nếu–thì đọc được.
- Phân loại văn bản trên nội dung bài đánh giá.

Mỗi mô hình đều kèm phần đánh giá độ chính xác, không chỉ báo cáo kết quả.

**4. Dashboard**

Giao diện kéo-thả để tự khám phá dữ liệu theo các chiều của kho, kèm các truy vấn mẫu đóng gói sẵn theo từng câu hỏi nghiệp vụ.

**5. Phần mở rộng** *(làm sau khi bốn phần trên hoàn thành)*

Gom nhóm chủ đề trên bài đánh giá tiêu cực để bóc tách nguyên nhân người chơi không hài lòng. Trợ lý truy vấn bằng câu hỏi tiếng Việt tự nhiên.

---

## Dữ liệu lấy từ đâu

Bốn nguồn, tất cả là API công khai, không cần trả phí và không vi phạm điều khoản sử dụng:

| Nguồn | Dữ liệu | Tần suất |
|---|---|---|
| Steam Web API | Số người chơi đồng thời | Theo giờ |
| Steam Store API | Tên, loại ứng dụng, giá, % giảm giá, thể loại, tính năng, ngày phát hành, nhà phát hành, số ngôn ngữ hỗ trợ | Theo tuần |
| SteamSpy API | Tag do người chơi bình chọn kèm số vote, khoảng người sở hữu, thời lượng chơi trung bình | Theo tuần |
| Steam Reviews API | Nội dung bài đánh giá, nhãn thích/không thích, tổng số review | Theo ngày |

**Vì sao cần cả bốn nguồn.** Không nguồn nào đủ một mình, và giữa chúng có xung đột thật phải giải quyết:

- Store API không trả về tag do người chơi bình chọn, chỉ có 13 thể loại cấp cao. Các tag ngách như Roguelite hay Souls-like — thứ làm nên giá trị của phần khai phá luật kết hợp — chỉ có ở SteamSpy.
- Số review tích cực/tiêu cực có ở cả SteamSpy và Reviews API nhưng lệch nhau, vì SteamSpy là dữ liệu cache. Cần quy tắc chọn nguồn ưu tiên.
- Giá ở SteamSpy tính bằng USD, ở Store API bằng VNĐ và có hệ số nhân. Cần chuẩn hóa về một đơn vị.
- Thể loại ở một nguồn là mảng đối tượng, ở nguồn kia là chuỗi; khoảng người sở hữu là văn bản phải tách thành hai giá trị số.

Chính việc hợp nhất bốn nguồn lệch nhau này là phần tích hợp dữ liệu của đề tài.

**Về dữ liệu lịch sử.** Steam không cho lấy lịch sử lượng người chơi hay giá — hệ thống tích lũy từ lúc bật pipeline. Các thuộc tính không đổi theo thời gian (ngày phát hành, nhà phát hành, tag, thể loại) được nạp nền từ bộ dữ liệu công khai để chạy được khai phá ngay từ đầu. Riêng các chỉ số đếm được (số review, người chơi, người sở hữu) chỉ lấy từ pipeline tự thu, không lấy từ bộ nền — vì con số trong bộ nền là giá trị ở thời điểm dump, dùng làm đặc trưng cho mô hình dự đoán sẽ là dùng thông tin tương lai.

---

## Công cụ

| Tầng | Công nghệ |
|---|---|
| Lưu dữ liệu thô | MinIO (object storage tương thích S3) |
| Kho dữ liệu | PostgreSQL |
| Điều phối luồng | Apache Airflow |
| Biến đổi dữ liệu | SQLMesh |
| Dashboard | Metabase |
| Khai phá dữ liệu | Python — pandas, scikit-learn, mlxtend |
| Triển khai | Docker Compose |
| Cảnh báo pipeline | Telegram Bot |

Toàn bộ là mã nguồn mở, miễn phí, chạy trên một máy cá nhân, khởi động bằng một lệnh nên dễ tái lập khi chấm.

Kiến trúc theo hướng nạp thô trước rồi biến đổi sau, thay vì biến đổi trước khi nạp. Lý do: dữ liệu gốc luôn còn nguyên trong data lake, nên khi phát hiện sai ở tầng biến đổi thì chỉ cần chạy lại phép biến đổi, không phải gọi lại API.

---

## Câu hỏi hệ thống trả lời

**Truy vấn đa chiều**

1. **Đường cong người chơi trong 24 giờ khác nhau thế nào giữa các thể loại?** Xoay trục theo giờ × thể loại. Game co-op và nhiều người chơi dự kiến có đỉnh dồn vào buổi tối, game một người chơi phân bố đều hơn. → Đội vận hành chọn khung giờ ra bản cập nhật, chạy sự kiện, hoặc bảo trì server.

2. **Hiệu ứng cuối tuần mạnh đến đâu, và khác nhau giữa các nhóm game thế nào?** Xoay trục theo thứ trong tuần, so lượng người chơi cuối tuần với ngày thường. → Chọn thời điểm phát hành DLC hoặc mở chơi thử miễn phí.

3. **Mức giá thị trường đang chấp nhận cho từng thể loại là bao nhiêu?** Cắt lát theo game trả phí, cắt khối theo thể loại và khoảng giá. → Studio độc lập định giá sản phẩm mới dựa trên phân bố giá thực tế của thể loại mình.

4. **Số game phát hành mới thay đổi thế nào theo thời gian và thể loại?** Tổng hợp từ tháng lên quý lên năm, rồi khoan xuống từng thể loại. → Đánh giá mức cạnh tranh của một thể loại trước khi bước vào.

5. *(mở rộng)* **Mức giảm giá bao nhiêu tạo hiệu ứng tăng người chơi tốt nhất?** Xoay trục theo trạng thái trong/ngoài sale × mức giảm. Câu này phụ thuộc việc có một đợt Steam Sale rơi trong thời gian thu thập, nên xếp là phần mở rộng chứ không phải trục chính.

**Khai phá dữ liệu**

6. **Tổ hợp tag nào thường đi cùng nhau, và tổ hợp nào gắn với tỷ lệ đánh giá tích cực cao?** Mỗi game là một giao dịch, các tag là các mặt hàng — bài toán giỏ hàng. → Studio chọn tổ hợp thể loại và yếu tố gameplay khi lên ý tưởng, biết tổ hợp nào thị trường đang đón nhận.

7. **Thị trường Steam phân tầng thành những nhóm nào?** Phân cụm theo lượng người chơi, giá, tỷ lệ đánh giá tích cực, thời lượng chơi. Số cụm được chọn từ dữ liệu, tên cụm đặt sau khi xem đặc trưng thực tế của từng cụm. → Nhà phát hành định vị một game trong bức tranh thị trường, nhận diện game có dấu hiệu định giá cao hơn giá trị người chơi cảm nhận.

8. **Yếu tố nào biết được trước khi phát hành có liên hệ với việc game trở thành nhóm hiệu suất cao?** Cây quyết định, đặc trưng chỉ gồm thông tin có sẵn trước ngày phát hành: số game nhà phát hành đã ra trước đó, số ngôn ngữ hỗ trợ, có chế độ nhiều người chơi, có co-op, các tag chính. → Studio biết nên đầu tư vào bản địa hóa hay vào chế độ multiplayer; quỹ đầu tư sàng lọc hồ sơ xin tài trợ.

9. **Có dự đoán được thái độ người chơi từ nội dung bài đánh giá không, chính xác đến đâu?** Phân loại văn bản, nhãn là thích/không thích do chính người viết gán nên có sẵn nhãn đúng để đo. → Nền tảng cho việc tự động phân loại phản hồi ở quy mô lớn.

10. *(mở rộng)* **Người chơi phàn nàn về những nhóm vấn đề nào?** Gom nhóm chủ đề trên tập đánh giá tiêu cực. → Đội phát triển xếp thứ tự ưu tiên sửa lỗi sau một bản cập nhật.

---

## Giới hạn đã nhận diện

- Steam không công bố số lượng bán, nên hệ thống không dự báo doanh thu. Số người sở hữu là khoảng ước lượng của bên thứ ba và được trình bày đúng như vậy.
- Cửa sổ dữ liệu chỉ bằng thời gian làm đồ án, nên các câu hỏi cần nhiều năm lịch sử không nằm trong phạm vi.
- Tần suất lấy mẫu không đồng nhất giữa các nhóm game do giới hạn API. Bảng tổng hợp ghi kèm số mẫu thu được để mọi phân tích biết độ tin cậy của từng dòng, và chỉ số đỉnh người chơi chỉ so sánh giữa các game có cùng mật độ lấy mẫu.
