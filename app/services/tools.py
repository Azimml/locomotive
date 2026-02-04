from __future__ import annotations

locomotive_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_total_locomotives_count",
            "description": "Jami lokomotivlar sonini olish. Foydalaning: 'Nechta lokomotiv bor?', 'Lokomotivlar soni', 'Jami lokomotivlar'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locomotives_by_state",
            "description": "Holatiga qarab lokomotivlarni olish. Foydalaning: 'Foydalanishdagi lokomotivlar', 'Tamirdagi lokomotivlar', 'Rezervdagi lokomotivlar', 'Ishlaydigan lokomotivlar'",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["in_use", "in_inspection", "in_reserve", "all"],
                        "description": "Holat: in_use (foydalanishda), in_inspection (tamirda), in_reserve (rezervda), all (hammasi)",
                    }
                },
                "required": ["state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Umumiy statistikani olish: jami lokomotivlar, modellar soni va holat bo'yicha taqsimot. Foydalaning: 'Statistika', 'Umumiy ma'lumot', 'Holat bo'yicha statistika'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locomotive_types",
            "description": "Lokomotiv turlarini va ularning sonini olish. Foydalaning: 'Lokomotiv turlari', 'Elektrovozlar soni', 'Teplovozlar soni', 'Qanday turdagi lokomotivlar bor?'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locomotive_models",
            "description": "Lokomotiv modellarini olish. Foydalaning: 'Lokomotiv modellari', 'Qanday modellar bor?', 'UZ-EL modeli haqida'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_repairs",
            "description": "Hozirda tamirda bo'lgan lokomotivlarni olish. Foydalaning: 'Tamirdagi lokomotivlar', 'Faol ta'mirlar', 'Hozir qaysi lokomotivlar tamirda?'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locomotive_last_repair",
            "description": "Aniq bir lokomotivning oxirgi ta'miri haqida ma'lumot. Foydalaning: '026 lokomotivning oxirgi ta'miri', 'Lokomotiv 1255 qachon ta'mirlangan?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "locomotive_name": {
                        "type": "string",
                        "description": "Lokomotiv nomi yoki raqami (masalan: 026, 1255)",
                    }
                },
                "required": ["locomotive_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_last_repairs",
            "description": "Barcha lokomotivlarning oxirgi ta'mirlari ro'yxati. Foydalaning: 'Oxirgi ta'mirlar ro'yxati', 'Barcha ta'mirlar'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_locomotive_by_name",
            "description": "Lokomotivni nomi bo'yicha qidirish. Agar noaniq raqam berilsa (masalan: '020'), o'xshash barcha lokomotivlarni topadi va variantlarni taklif qiladi. Foydalanuvchi aniq raqam tanlasa, batafsil ma'lumot beradi. Foydalaning: '020 lokomotivi', 'Lokomotiv 1255 holati', '0207 haqida'",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Lokomotiv nomi yoki raqami. To'liq yoki qisman bo'lishi mumkin (masalan: 020, 0207, 1255)",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locomotive_detailed_info",
            "description": "Aniq bir lokomotiv haqida batafsil ma'lumot olish: joylashuvi, deposi, ta'mir tarixi, yillik ta'mirlar soni va kelgusi tekshiruvlar. Foydalaning: '0406 lokomotivi haqida batafsil', '0204 vagonning ta'mir tarixi', '1255 qaysi depoda?', 'TO2 tamiri qachon bo'lgan?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "locomotive_name": {
                        "type": "string",
                        "description": "Lokomotiv raqami (masalan: 0406, 0204, 1255). Faqat raqamni kiriting.",
                    }
                },
                "required": ["locomotive_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_inspections",
            "description": "Hozirda qanday tekshiruvlar (inspeksiyalar) bo'layotganini va har bir tekshiruv turida nechta lokomotiv borligini ko'rsatadi. Foydalaning: 'Hozir qancha lokomotiv tekshiruvda?', 'TXK-2 da nechta lokomotiv bor?', 'Joriy inspeksiyalar', 'Hozirgi ta'mirlar holati'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_inspection_counts",
            "description": "Umumiy tekshiruv (inspeksiya) statistikasi - har bir tekshiruv turida jami nechta lokomotiv tekshirilganligini ko'rsatadi. Foydalaning: 'Umumiy tekshiruv statistikasi', 'Jami nechta TXK-2 bo'lgan?', 'Inspeksiya hisoboti'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_depo_info",
            "description": "Aniq bir depo haqida batafsil ma'lumot: lokomotivlar soni, turlari va holatlari. Foydalaning: 'Qo'qon deposi haqida', 'Chuqursoy deposi statistikasi', 'Andijon deposida nechta lokomotiv bor?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "depo_id": {
                        "type": "number",
                        "description": "Depo ID raqami (1-Chuqursoy, 2-Andijon, 3-Termez, 4-Qarshi, 5-Tinchlik, 6-Buxoro, 7-Urganch, 8-Qo'ng'irot, 9-Liniyada)",
                    }
                },
                "required": ["depo_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_depos_info",
            "description": "Barcha depolar haqida umumiy ma'lumot: har bir depodagi lokomotivlar soni, turlari va holatlari. Foydalaning: 'Barcha depolar statistikasi', 'Depolar ro'yxati', 'Qaysi depoda qancha lokomotiv bor?', 'Depo ma'lumotlari'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repair_stats_by_year",
            "description": "Yillar bo'yicha ta'mir statistikasi: har bir yilda qancha va qanday ta'mirlar bo'lganligini ko'rsatadi. Foydalaning: '2025 yilda qancha ta'mir bo'lgan?', 'Yillik ta'mir statistikasi', 'Bu yil nechta JT-1 bo'ldi?', 'Ta'mirlar tarixi'",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
