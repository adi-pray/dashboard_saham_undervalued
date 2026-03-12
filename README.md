# Professional Stock Screener

Aplikasi Streamlit untuk screening saham berbasis pendekatan value investing sederhana dengan data dari Yahoo Finance.

## File
- `app.py` — aplikasi utama Streamlit
- `requirements.txt` — dependency untuk deploy
- `.streamlit/config.toml` — konfigurasi UI dasar Streamlit

## Jalankan lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy ke Streamlit Cloud
1. Upload file ini ke repository GitHub.
2. Buka Streamlit Cloud.
3. Pilih repository dan branch.
4. Set main file path ke `app.py`.
5. Deploy.

## Catatan
Fair value di aplikasi ini masih memakai pendekatan sederhana:

`Fair Value = EPS × 15`

Gunakan untuk screening awal, bukan sebagai satu-satunya dasar keputusan investasi.
