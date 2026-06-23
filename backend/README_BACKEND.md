# DAPROS Web + FastAPI

## Cara menjalankan backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Backend aktif di:

```text
http://127.0.0.1:8000
```

## Cara menjalankan frontend

Buka terminal baru dari folder utama project:

```bash
python -m http.server 5500
```

Lalu buka:

```text
http://localhost:5500
```

## Sistem 3 - Pembagian Data

Alur sudah disesuaikan dengan Colab `Pembagian_Data.ipynb`:

1. Upload file hasil Sistem 2.
2. Backend membaca sheet `Dapros_Bersih` dan `Dapros_Terfilter`.
3. Frontend menampilkan rekap WITEL dari data terfilter.
4. User mengisi jumlah VAM dari data bersih.
5. User mengisi nama tim bebas, contoh: `TAM, ISE, DGS`.
6. Klik `Buat Form Alokasi`.
7. User mengisi alokasi per WITEL untuk setiap tim.
8. Klik `Proses Pembagian Data`.
9. Output berupa ZIP berisi:
   - `hasil_pembagian_vam_tam_ise.xlsx`
   - `sisa_data_belum_kepakai.xlsx`
