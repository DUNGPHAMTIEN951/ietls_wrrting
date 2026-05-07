const TASK1_FLASHCARDS = {
    'Sự gia tăng': [
        { front: 'rise', back: 'Sự gia tăng', hint: 'verb/noun' },
        { front: 'increase', back: 'Sự gia tăng', hint: 'verb/noun' },
        { front: 'climb', back: 'Sự gia tăng', hint: 'verb/noun' },
        { front: 'go up', back: 'Sự gia tăng', hint: 'phrasal verb' },
        { front: 'grow', back: 'Sự gia tăng', hint: 'verb' },
        { front: 'improve', back: 'Sự cải thiện/gia tăng', hint: 'verb' }
    ],
    'Sự tăng mạnh': [
        { front: 'soar', back: 'Tăng vọt', hint: 'verb' },
        { front: 'rocket', back: 'Tăng rất mạnh', hint: 'verb' },
        { front: 'boom', back: 'Bùng nổ', hint: 'verb/noun' },
        { front: 'leap', back: 'Nhảy vọt', hint: 'verb/noun' },
        { front: 'shoot up', back: 'Tăng vọt', hint: 'phrasal verb' },
        { front: 'surge', back: 'Tăng mạnh đột ngột', hint: 'verb/noun' }
    ],
    'Sự suy giảm': [
        { front: 'decrease', back: 'Sự suy giảm', hint: 'verb/noun' },
        { front: 'drop', back: 'Giảm xuống', hint: 'verb/noun' },
        { front: 'decline', back: 'Sụt giảm', hint: 'verb/noun' },
        { front: 'reduce', back: 'Làm giảm', hint: 'verb' },
        { front: 'fall', back: 'Rơi/Giảm', hint: 'verb/noun' },
        { front: 'go down', back: 'Giảm xuống', hint: 'phrasal verb' },
        { front: 'diminish', back: 'Giảm bớt', hint: 'verb' }
    ],
    'Sự giảm mạnh': [
        { front: 'plummet', back: 'Rơi thẳng đứng', hint: 'verb' },
        { front: 'plunge', back: 'Lao dốc', hint: 'verb/noun' },
        { front: 'collapse', back: 'Sụp đổ/Giảm cực mạnh', hint: 'verb/noun' },
        { front: 'sink', back: 'Chìm xuống/Giảm sâu', hint: 'verb' },
        { front: 'crash', back: 'Sụt giảm nghiêm trọng', hint: 'verb/noun' }
    ],
    'Sự dao động': [
        { front: 'fluctuate', back: 'Dao động lên xuống', hint: 'verb' },
        { front: 'witness ups and downs', back: 'Chứng kiến sự thăng trầm', hint: 'phrase' }
    ],
    'Sự ổn định': [
        { front: 'remain unchanged', back: 'Duy trì không đổi', hint: 'phrase' },
        { front: 'steady', back: 'Vững chắc/Ổn định', hint: 'adj' },
        { front: 'constant', back: 'Liên tục/Không đổi', hint: 'adj' },
        { front: 'maintain the same level', back: 'Duy trì cùng mức độ', hint: 'phrase' },
        { front: 'stabilize', back: 'Ổn định lại', hint: 'verb' },
        { front: 'stay at', back: 'Ở mức', hint: 'phrase' },
        { front: 'stand at', back: 'Đứng ở mức', hint: 'phrase' }
    ],
    'Mức độ': [
        { front: 'slight(ly)', back: 'Nhẹ/Chút ít', hint: 'adj/adv' },
        { front: 'gradual(ly)', back: 'Dần dần', hint: 'adj/adv' },
        { front: 'minimal(ly)', back: 'Tối thiểu/Rất ít', hint: 'adj/adv' },
        { front: 'noticeable(bly)', back: 'Đáng chú ý', hint: 'adj/adv' },
        { front: 'marked(ly)', back: 'Rõ rệt', hint: 'adj/adv' },
        { front: 'moderate(ly)', back: 'Vừa phải', hint: 'adj/adv' },
        { front: 'substantial(ly)', back: 'Đáng kể', hint: 'adj/adv' },
        { front: 'considerable(bly)', back: 'Đáng kể/To lớn', hint: 'adj/adv' },
        { front: 'remarkable(bly)', back: 'Đáng chú ý/Xuất sắc', hint: 'adj/adv' },
        { front: 'significant(ly)', back: 'Đáng kể/Quan trọng', hint: 'adj/adv' },
        { front: 'dramatic(ally)', back: 'Đột ngột/Đáng kể', hint: 'adj/adv' },
        { front: 'huge/enormous(ly)', back: 'Khổng lồ/Rất lớn', hint: 'adj/adv' },
        { front: 'tremendous(ly)', back: 'Ghê gớm/To lớn', hint: 'adj/adv' }
    ],
    'Trình tự': [
        { front: 'Firstly/Secondly', back: 'Thứ nhất/Thứ hai', hint: 'ordering' },
        { front: 'Next/Then', back: 'Tiếp theo/Sau đó', hint: 'ordering' },
        { front: 'After that', back: 'Sau đó', hint: 'ordering' },
        { front: 'Following this', back: 'Theo sau điều này', hint: 'ordering' },
        { front: 'Finally', back: 'Cuối cùng', hint: 'ordering' },
        { front: 'In the first stage', back: 'Ở giai đoạn đầu tiên', hint: 'process' },
        { front: 'In the final stage', back: 'Ở giai đoạn cuối cùng', hint: 'process' }
    ],
    'Vị trí': [
        { front: 'in the North/South', back: 'Ở hướng Bắc/Nam', hint: 'location' },
        { front: 'on the left/right', back: 'Bên trái/phải', hint: 'location' },
        { front: 'next to', back: 'Phụ cận/Kế bên', hint: 'location' },
        { front: 'opposite', back: 'Đối diện', hint: 'location' },
        { front: 'converted into', back: 'Được chuyển đổi thành', hint: 'change' },
        { front: 'replaced by', back: 'Được thay thế bởi', hint: 'change' },
        { front: 'extended', back: 'Được mở rộng', hint: 'change' },
        { front: 'removed', back: 'Bị xóa bỏ/Dời đi', hint: 'change' }
    ]
};