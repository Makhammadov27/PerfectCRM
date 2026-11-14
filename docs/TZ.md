# O'quv markaz platformasi — Texnik topshiriq (v0.1)

> Loyiha nomi vaqtincha: **PerfectCRM** (keyin o'zgaradi).

## 1. Umumiy

- Platforma **VPS (bulut)** da ishlaydi; admin kompyuterdan brauzer orqali kiradi.
- O'qituvchilar davomatni **Telegram bot** orqali oladi (ota-onalar bilan bitta bot, rol telefon raqamidan aniqlanadi).
- Ota-onalar **Telegram bot** orqali xabar oladi; Telegrami yo'qlarga **SMS (Eskiz.uz)**.
- Valyuta: so'm, butun son (tiyinsiz).

## 2. Rollar

| Rol | Imkoniyatlar |
|---|---|
| **Admin** | Hammasi: o'quvchi, o'qituvchi, guruh, xona, to'lov, maosh, hisobot, sozlamalar, davomatni tahrirlash |
| **O'qituvchi** (bot) | Faqat o'z guruhlari, bugungi darslar va davomat olish (faqat dars vaqtida) |
| **Ota-ona** (bot) | Farzandi davomati, qarzi, to'lov cheklari |

Rollar ruxsatlar (permissions) asosida — keyin "Kassir", "Menejer" qo'shish oson bo'lsin.

## 3. To'lov qoidalari

### 3.1 Narx
- Har bir **guruh** sozlamasida: `oylik_narx` (masalan 300 000) va `dars_narxi` (masalan 25 000).
- Standart: haftasiga 3 dars, oyiga 12 dars × 25 000 = 300 000.

### 3.2 Oylik hisob (invoice)
- Har oy 1-kuni har bir faol o'quvchi uchun har bir guruhi bo'yicha hisob yaratiladi.
- **To'liq oy** → `oylik_narx` (oyda 13 dars bo'lsa ham 300 000).
- Pul **jadvaldagi barcha darslar uchun** olinadi (o'quvchi kelmasa ham).
- To'lov muddati: har oyning **5-kuni** (sozlamada o'zgaradi).

### 3.3 Oy o'rtasida qo'shilgan o'quvchi
```
summa = min(qolgan_darslar_soni × dars_narxi, oylik_narx)
```
`qolgan_darslar_soni` — qo'shilgan kundan oy oxirigacha guruh jadvalidagi darslar soni.

**Misol:** Guruh Du/Chor/Ju, o'quvchi 2026-yil 15-noyabrda qo'shildi.
Darslar: 16, 18, 20, 23, 25, 27, 30 → 7 dars × 25 000 = **175 000 so'm**.
Birinchi oy hisobining muddati — qo'shilgan kundan +5 kun (sozlamada).

### 3.4 Chegirma
- O'quvchi–guruh bog'lanishida: foiz yoki qat'iy summa (sababi yoziladi).

### 3.5 To'lovlar va qarz
- To'lov o'quvchiga yoziladi va avtomatik eng eski qarzga taqsimlanadi.
- `qarz = Σ hisoblar − Σ to'lovlar`. Ortiqcha to'lov — keyingi oyga avans.
- To'lov usuli: naqd / karta / o'tkazma (keyin Click/Payme).
- To'lov **o'chirilmaydi** — faqat **bekor qilinadi** (sabab + kim bekor qilgani).
- Har bir to'lovga **chek**: 80/58 mm chop etish, raqam, QR-kod (tekshirish havolasi).

### 3.6 Oy o'rtasida ketgan o'quvchi — pul qaytariladi
```
shu_oy_summasi = min(ketgan_kungacha_bo'lgan_darslar × dars_narxi, oylik_narx)
qaytariladi   = shu_oy_uchun_to'langan − shu_oy_summasi   (agar > 0)
```
- Oylik hisob `shu_oy_summasi` ga kamaytiriladi (eski summa audit logda qoladi).
- Qaytarilgan pul alohida **qaytarish (refund)** yozuvi bo'ladi: summa, sana, kim berdi, sabab — kassa hisobotida ko'rinadi.
- **Misol:** Du/Chor/Ju guruh, 300 000 to'langan, o'quvchi 2026-yil 13-noyabrda (oxirgi darsi) ketdi.
  Darslar: 2, 4, 6, 9, 11, 13 → 6 × 25 000 = 150 000 → **150 000 qaytariladi**.

### 3.7 Markaz darsni bekor qilsa
- Oylik summa **kamaymaydi** — dars boshqa kunga **almashtiriladi** (qo'shimcha dars).
- Bekor qilingan dars `cancelled`, o'rniga yangi dars (`makeup`, qaysi dars o'rniga ekani) yaratiladi;
  xona/o'qituvchi to'qnashuvi tekshiriladi, ota-onalarga bot orqali xabar boradi.

### 3.8 Muzlatish
- Kerak emas.

## 4. Davomat

- O'qituvchi **faqat o'z guruhini** va **faqat dars vaqtida** belgilaydi
  (masalan, dars boshlanishidan 15 daqiqa oldin — tugaganidan 2 soat keyin; sozlamada).
- Holatlar: **keldi / kelmadi / sababli / kechikdi**.
- Saqlangandan keyin o'zgartirish — **faqat admin** (o'zgarish audit logga yoziladi).
- **Botda davomat olish**: 📋 Davomat olish → bugungi darslar → dars → o'quvchilar ro'yxati
  (hammasi ✅ dan boshlanadi, bosilganda ✅ → ❌ → ⏰ → 🟡) → 💾 Saqlash.
  Oflayn rejim yo'q (Telegram internet talab qiladi); dars oynasi yetarlicha keng.
- O'quvchi **kelmasa yoki kechiksa** → ota-onaga darhol bot (yo'q bo'lsa SMS) xabari.

## 5. Guruh, xona, jadval

- Guruh: nomi, kurs/fan, o'qituvchi, xona, narxlar, boshlanish sanasi, holati.
- Jadval: hafta kunlari + boshlanish/tugash vaqti (masalan Du/Chor/Ju 14:00–15:30).
- **To'qnashuv nazorati**: bitta xonada yoki bitta o'qituvchida bir vaqtda 2 ta dars bo'lmaydi.
- Haftalik jadval ko'rinishi (xonalar × vaqt).

## 6. O'qituvchi maoshi

- Admin oy uchun summani **qo'lda kiritadi** va "to'landi" deb belgilaydi (sana, izoh).
- Avtomatik hisob yo'q.

## 7. Xabarnomalar

| Hodisa | Kanal |
|---|---|
| Kelmadi / kechikdi | Bot → (yo'q bo'lsa) SMS |
| To'lov eslatmasi: muddatdan 3 kun oldin, muddat kuni, kechikkanda | Bot → SMS |
| To'lov qabul qilindi + chek | Bot |

- Ota-ona botda `/start` → telefon raqamini ulashadi → bazadagi raqam bilan moslashtiriladi.
- SMS matnlari shablon sifatida sozlanadi; har bir SMS jurnalga yoziladi (holat, narx).

## 8. Hisobotlar (Excel eksport bilan)

- Oylik tushum (usul bo'yicha), qarzdorlar ro'yxati, davomat foizi (guruh/o'quvchi bo'yicha),
  o'qituvchilarga to'langan maoshlar.

## 9. Xavfsizlik

- HTTPS, parollar hash, JWT/sessiya.
- **Audit log**: kim, qachon, nimani o'zgartirdi (to'lov, davomat, narx).
- Har kecha avtomatik backup, nusxasi serverdan tashqariga.

## 10. Ma'lumotlar bazasi sxemasi (asosiy jadvallar)

```
users            id, phone, full_name, password_hash, role(admin|teacher), is_active
students         id, full_name, phone, birth_date, note, status(active|left), created_at
parents          id, student_id, full_name, phone, telegram_chat_id
rooms            id, name, capacity
groups           id, name, subject, teacher_id→users, room_id→rooms,
                 monthly_price, lesson_price, start_date, end_date, status
group_schedule   id, group_id, weekday(1-7), start_time, end_time
enrollments      id, student_id, group_id, joined_at, left_at,
                 discount_type(none|percent|fixed), discount_value, discount_reason
lessons          id, group_id, date, start_time, end_time, room_id,
                 status(planned|done|cancelled), kind(regular|makeup), replaces_lesson_id
attendance       id, lesson_id, student_id, status(present|absent|excused|late),
                 marked_by→users, marked_at, updated_by, updated_at
invoices         id, enrollment_id, period(YYYY-MM), lessons_count, base_amount, amount, paid_amount,
                 discount, due_date, status(open|paid|partial|void)
payments         id, student_id, amount, method(cash|card|transfer), paid_at,
                 receipt_no, received_by→users, cancelled_at, cancelled_by, cancel_reason

refunds          id, student_id, amount, paid_at, given_by→users, reason
salary_payments  id, teacher_id→users, period(YYYY-MM), amount, paid_at, note, created_by
notifications    id, parent_id, channel(telegram|sms), type, text, status, cost, sent_at
settings         key, value   (to'lov muddati kuni, davomat oynasi, SMS shablonlar...)
audit_log        id, user_id, action, entity, entity_id, before(json), after(json), at
```

## 11. MVP bosqichlari

1. Auth + rollar, o'quvchi / o'qituvchi / xona / guruh / jadval (to'qnashuv nazorati bilan)
2. Davomat (o'qituvchi Telegram bot orqali)
3. Hisoblar, to'lovlar, qarz, chek
4. Telegram bot + Eskiz SMS + eslatmalar
5. Hisobotlar + Excel, audit log, backup, deploy
