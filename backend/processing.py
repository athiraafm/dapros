from __future__ import annotations

from pathlib import Path
import re
import zipfile
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

RANDOM_STATE = 42


def _clean_str(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def _norm_name(value: str) -> str:
    """Normalisasi nama sheet/kolom agar tetap kebaca walau beda spasi/underscore/huruf."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _find_sheet(xls: pd.ExcelFile, candidates: List[str]) -> str | None:
    sheet_map = {_norm_name(sheet): sheet for sheet in xls.sheet_names}
    for candidate in candidates:
        found = sheet_map.get(_norm_name(candidate))
        if found:
            return found
    return None


def _read_sheet_or_empty(input_path: Path, xls: pd.ExcelFile, candidates: List[str]) -> pd.DataFrame:
    sheet = _find_sheet(xls, candidates)
    if not sheet:
        return pd.DataFrame()
    df = pd.read_excel(input_path, sheet_name=sheet, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    return df


def _read_sheet_or_first(input_path: Path, xls: pd.ExcelFile, candidates: List[str]) -> pd.DataFrame:
    sheet = _find_sheet(xls, candidates) or xls.sheet_names[0]
    df = pd.read_excel(input_path, sheet_name=sheet, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    return df


def create_dapros(input_path: Path, output_path: Path) -> Dict[str, int | str]:
    xls = pd.ExcelFile(input_path)
    if "Detail2" in xls.sheet_names:
        sheet_name = "Detail2"
    elif "Detail1" in xls.sheet_names:
        sheet_name = "Detail1"
    else:
        sheet_name = xls.sheet_names[0]

    preview = pd.read_excel(input_path, sheet_name=sheet_name, header=None, dtype=str, nrows=30)
    header_row = None
    for i in range(len(preview)):
        row_values = preview.iloc[i].fillna("").astype(str).str.upper().str.strip().tolist()
        if ("NCLI" in row_values) and ("NAMA" in row_values):
            header_row = i
            break
    if header_row is None:
        raise ValueError("Header tidak ketemu. Pastikan ada kolom NCLI dan NAMA di file.")

    df = pd.read_excel(input_path, sheet_name=sheet_name, header=header_row, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all").copy()

    kol_nama = "NAMA"
    kol_ncli = "NCLI"
    kol_ekosistem = "EKOSISTEM2"
    kol_arpu = "ARPU"
    if "Speed (MBps)" in df.columns:
        kol_speed = "Speed (MBps)"
    elif "SPEED" in df.columns:
        kol_speed = "SPEED"
    else:
        raise ValueError("Kolom speed tidak ditemukan. Cek apakah namanya 'Speed (MBps)' atau 'SPEED'.")

    for kol in [kol_nama, kol_ncli, kol_ekosistem, kol_arpu, kol_speed, "NOHP"]:
        if kol not in df.columns:
            raise ValueError(f"Kolom wajib tidak ditemukan: {kol}")

    df[kol_nama] = df[kol_nama].fillna("").astype(str).str.strip()
    df[kol_ncli] = df[kol_ncli].fillna("").astype(str).str.strip()
    df[kol_ekosistem] = df[kol_ekosistem].fillna("").astype(str).str.lower().str.strip()
    df = df[(df[kol_ncli] != "") & (~df[kol_ncli].str.lower().isin(["nan", "none"]))].copy()

    df["NOHP"] = df["NOHP"].fillna("").astype(str).str.strip()
    df = df[(df["NOHP"] != "") & (~df["NOHP"].str.lower().isin(["nan", "none", "null", "na"]))].copy()
    digit_hp = df["NOHP"].str.replace(r"\D", "", regex=True)
    df = df[(digit_hp.str.len() >= 10) & (digit_hp.str.len() <= 12)].copy()

    kolom_offering_existing = ["OFF NETMONK", "OFF ANTARES", "OFF OCA", "OFF UPGRADE SPEED", "OFF UPGRADE SPEED2"]
    kolom_cek_produk = [c for c in df.columns if c not in kolom_offering_existing]
    teks_semua_kolom = df[kolom_cek_produk].fillna("").astype(str).agg(" ".join, axis=1).str.lower()

    sudah_netmonk = teks_semua_kolom.str.contains(r"\bnetmonk\b", regex=True, na=False)
    sudah_antares = teks_semua_kolom.str.contains(r"\bantares\b", regex=True, na=False)
    sudah_oca = teks_semua_kolom.str.contains(r"\boca\b", regex=True, na=False)

    multi_layanan = df.groupby([kol_nama, kol_ncli])[kol_ncli].transform("count") > 1
    banyak_cabang = df.groupby(kol_nama)[kol_ncli].transform("nunique") > 1

    arpu_clean = df[kol_arpu].fillna("").astype(str).str.replace(r"[^0-9]", "", regex=True)
    arpu = pd.to_numeric(arpu_clean, errors="coerce").fillna(0)
    speed_text = df[kol_speed].fillna("").astype(str).str.upper().str.strip()
    speed_num = pd.to_numeric(speed_text.str.replace(r"[^0-9]", "", regex=True), errors="coerce")
    speed_valid = speed_num.notna()
    speed_mbps = speed_num / 1024

    eko_netmonk = df[kol_ekosistem].str.contains(r"hotel|manufaktur|manufactur|multi finance|multifinance|sekolah|energi|energy", regex=True, na=False)
    eko_oca = df[kol_ekosistem].str.contains(r"ruko|umkm|media|comm|communication|komunikasi|multi finance|multifinance|property|properti", regex=True, na=False)
    kategori_oca = teks_semua_kolom.str.contains(r"online shop|onlineshop|retail|food|beverage|fnb|f&b|fashion", regex=True, na=False)

    netmonk_rule = (~sudah_netmonk) & (multi_layanan | banyak_cabang | eko_netmonk)
    antares_rule = (~sudah_antares) & (arpu > 500000)
    oca_rule = (~sudah_oca) & (eko_oca | kategori_oca)
    upgrade_speed_result = np.select(
        [speed_valid & (speed_mbps < 50), speed_valid & (speed_mbps >= 50) & (speed_mbps <= 75)],
        ["Upgrade Speed <50 Mbps", "Upgrade Speed 50-75 Mbps"],
        default="",
    )

    df["OFF NETMONK"] = np.where(netmonk_rule, "Netmonk", "")
    df["OFF ANTARES"] = np.where(antares_rule, "Antares", "")
    df["OFF OCA"] = np.where(oca_rule, "OCA", "")
    df["OFF UPGRADE SPEED"] = upgrade_speed_result

    summary = pd.DataFrame({
        "Offering": ["OFF NETMONK", "OFF ANTARES", "OFF OCA", "OFF UPGRADE SPEED"],
        "Jumlah": [(df["OFF NETMONK"] != "").sum(), (df["OFF ANTARES"] != "").sum(), (df["OFF OCA"] != "").sum(), (df["OFF UPGRADE SPEED"] != "").sum()],
    })

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Detail_Rekomendasi", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)

    return {"sheet": sheet_name, "total": int(len(df)), "netmonk": int((df["OFF NETMONK"] != "").sum()), "antares": int((df["OFF ANTARES"] != "").sum()), "oca": int((df["OFF OCA"] != "").sum()), "upgrade": int((df["OFF UPGRADE SPEED"] != "").sum())}


def extract_ncli_from_excel(filepath: Path, kolom_target: str = "NCLI") -> set[str]:
    ncli = set()
    xls = pd.ExcelFile(filepath)
    for sheet in xls.sheet_names:
        df = pd.read_excel(filepath, sheet_name=sheet, dtype=str)
        df.columns = df.columns.astype(str).str.strip()
        if kolom_target in df.columns:
            vals = _clean_str(df[kolom_target]).tolist()
            ncli.update(v for v in vals if v and v.lower() not in {"nan", "none", "null"})
    return ncli


def filter_ncli(dapros_path: Path, historis_paths: List[Path], output_path: Path) -> Dict[str, int]:
    try:
        df = pd.read_excel(dapros_path, sheet_name="Detail_Rekomendasi", dtype=str)
    except Exception:
        df = pd.read_excel(dapros_path, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    if "NCLI" not in df.columns:
        raise ValueError("Kolom NCLI tidak ditemukan di file DAPROS.")
    df["NCLI"] = _clean_str(df["NCLI"])

    semua_ncli = set()
    for p in historis_paths:
        semua_ncli.update(extract_ncli_from_excel(p, "NCLI"))
    semua_ncli.discard("nan")

    mask_terfilter = df["NCLI"].isin(semua_ncli)
    df_terfilter = df[mask_terfilter].copy()
    df_bersih = df[~mask_terfilter].copy()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_bersih.to_excel(writer, sheet_name="Dapros_Bersih", index=False)
        df_terfilter.to_excel(writer, sheet_name="Dapros_Terfilter", index=False)
        pd.DataFrame({"Keterangan": ["Total Awal", "Dapros Bersih", "Dapros Terfilter"], "Jumlah": [len(df), len(df_bersih), len(df_terfilter)]}).to_excel(writer, sheet_name="Summary", index=False)

    return {"total": int(len(df)), "bersih": int(len(df_bersih)), "terfilter": int(len(df_terfilter)), "historis_unik": int(len(semua_ncli))}


def get_witel_preview(input_path: Path) -> Dict:
    xls = pd.ExcelFile(input_path)

    print("=== DEBUG PEMBAGIAN PREVIEW ===")
    print("FILE:", input_path)
    print("SHEET TERBACA:", xls.sheet_names)

    clean_candidates = [
        "Dapros_Bersih", "Data_Bersih", "Dapros Bersih", "Data Bersih", "Bersih",
        "Dapros_Clean", "Data_Clean", "Dapros Clean", "Data Clean", "Clean",
        "Data_Tidak_Match", "Data Tidak Match", "Tidak Match", "Tidak_Match",
        "No_Match", "No Match"
    ]
    filter_candidates = [
        "Dapros_Terfilter", "Data_Terfilter", "Dapros Terfilter", "Data Terfilter", "Terfilter",
        "Dapros_Match", "Data_Match", "Dapros Match", "Data Match", "Match",
        "Filtered", "Dapros Filtered", "Dapros_Filtered"
    ]

    sheet_bersih = _find_sheet(xls, clean_candidates)
    sheet_terfilter = _find_sheet(xls, filter_candidates)

    print(f"sheet_bersih found: {sheet_bersih}, sheet_terfilter found: {sheet_terfilter}")

    if sheet_bersih and sheet_terfilter:
        df_bersih = pd.read_excel(input_path, sheet_name=sheet_bersih, dtype=str)
        df_bersih.columns = df_bersih.columns.astype(str).str.strip()
        
        df_terfilter = pd.read_excel(input_path, sheet_name=sheet_terfilter, dtype=str)
        df_terfilter.columns = df_terfilter.columns.astype(str).str.strip()
    else:
        first_sheet = xls.sheet_names[0]
        df_data = pd.read_excel(input_path, sheet_name=first_sheet, dtype=str)
        df_data.columns = df_data.columns.astype(str).str.strip()
        
        df_bersih = df_data
        df_terfilter = df_data

    print("TOTAL DAPROS_BERSIH:", len(df_bersih))
    print("KOLOM DAPROS_BERSIH:", df_bersih.columns.tolist())
    print("TOTAL DAPROS_TERFILTER:", len(df_terfilter))
    print("KOLOM DAPROS_TERFILTER:", df_terfilter.columns.tolist())

    if df_bersih.empty:
        print("WARNING: Dapros_Bersih terbaca kosong.")

    if "WITEL" not in df_terfilter.columns:
        raise ValueError(
            f"Kolom WITEL tidak ditemukan. "
            f"Sheet terbaca: {xls.sheet_names}. "
            f"Kolom data terfilter: {df_terfilter.columns.tolist()}"
        )

    df_terfilter["WITEL"] = df_terfilter["WITEL"].fillna("UNKNOWN").astype(str).str.strip()

    rekap = df_terfilter["WITEL"].value_counts().reset_index()
    rekap.columns = ["WITEL", "JUMLAH_DATA"]

    return {
        "total_terfilter": int(len(df_terfilter)),
        "total_bersih": int(len(df_bersih)),
        "total": int(len(df_terfilter)),
        "witels": [
            {
                "name": str(row.WITEL),
                "total": int(row.JUMLAH_DATA),
            }
            for row in rekap.itertuples(index=False)
        ],
    }

def pembagian_data(input_path: Path, allocations: Dict, zip_output_path: Path) -> Dict[str, int | str]:
    xls = pd.ExcelFile(input_path)

    clean_candidates = [
        "Dapros_Bersih", "Data_Bersih", "Dapros Bersih", "Data Bersih", "Bersih",
        "Dapros_Clean", "Data_Clean", "Dapros Clean", "Data Clean", "Clean",
        "Data_Tidak_Match", "Data Tidak Match", "Tidak Match", "Tidak_Match",
        "No_Match", "No Match"
    ]
    filter_candidates = [
        "Dapros_Terfilter", "Data_Terfilter", "Dapros Terfilter", "Data Terfilter", "Terfilter",
        "Dapros_Match", "Data_Match", "Dapros Match", "Data Match", "Match",
        "Filtered", "Dapros Filtered", "Dapros_Filtered"
    ]

    sheet_bersih = _find_sheet(xls, clean_candidates)
    sheet_terfilter = _find_sheet(xls, filter_candidates)

    if sheet_bersih and sheet_terfilter:
        df_bersih = pd.read_excel(input_path, sheet_name=sheet_bersih, dtype=str)
        df_bersih.columns = df_bersih.columns.astype(str).str.strip()
        
        df_terfilter = pd.read_excel(input_path, sheet_name=sheet_terfilter, dtype=str)
        df_terfilter.columns = df_terfilter.columns.astype(str).str.strip()
        is_disjoint = True
    else:
        first_sheet = xls.sheet_names[0]
        df_data = pd.read_excel(input_path, sheet_name=first_sheet, dtype=str)
        df_data.columns = df_data.columns.astype(str).str.strip()
        
        df_bersih = df_data
        df_terfilter = df_data
        is_disjoint = False

    df_bersih.columns = [str(c).strip() for c in df_bersih.columns]
    df_terfilter.columns = [str(c).strip() for c in df_terfilter.columns]
    if "WITEL" not in df_terfilter.columns:
        raise ValueError("Kolom WITEL tidak ditemukan di data terfilter.")
    df_terfilter["WITEL"] = df_terfilter["WITEL"].fillna("UNKNOWN")

    jumlah_vam = int(allocations.get("vam", 0) or 0)
    teams = allocations.get("teams", {}) or {}

    if jumlah_vam > len(df_bersih):
        raise ValueError("Jumlah VAM melebihi data bersih yang tersedia.")
    
    df_bersih_random = df_bersih.sample(frac=1, random_state=RANDOM_STATE) if len(df_bersih) else df_bersih.copy()
    vam_output = df_bersih_random.iloc[:jumlah_vam].copy()
    sisa_bersih = df_bersih_random.iloc[jumlah_vam:].copy()
    
    if len(vam_output): vam_output["PIC"] = "VAM"
    if len(sisa_bersih): sisa_bersih["PIC"] = "SISA_BERSIH"

    df_pool = df_terfilter.copy()
    if not is_disjoint:
        df_pool = df_pool.drop(index=vam_output.index, errors="ignore")
        sisa_bersih = pd.DataFrame(columns=df_bersih.columns)

    hasil_pic = {pic.upper(): [] for pic in teams.keys()}

    for pic, by_witel in teams.items():
        pic = pic.upper()
        for witel, jumlah in (by_witel or {}).items():
            jumlah = int(jumlah or 0)
            tersedia_idx = df_pool[df_pool["WITEL"].astype(str) == str(witel)].index
            if jumlah > len(tersedia_idx):
                raise ValueError(f"Jumlah {pic} untuk WITEL {witel} melebihi data tersedia.")
            if jumlah > 0:
                ambil = df_pool.loc[tersedia_idx].sample(n=jumlah, random_state=RANDOM_STATE).copy()
                ambil["PIC"] = pic
                hasil_pic[pic].append(ambil)
                df_pool = df_pool.drop(index=ambil.index)

    for pic in list(hasil_pic.keys()):
        if hasil_pic[pic]:
            hasil_pic[pic] = pd.concat(hasil_pic[pic], ignore_index=True)
        else:
            hasil_pic[pic] = pd.DataFrame(columns=df_terfilter.columns.tolist() + ["PIC"])

    sisa_terfilter = df_pool.copy()
    if len(sisa_terfilter): sisa_terfilter["PIC"] = "SISA_TERFILTER"

    kolom_bantu = ["cand_upgrade_high", "cand_upgrade_low", "cand_antares", "cand_netmonk", "cand_oca", "ALL_CANDIDATES", "FINAL_OFFERS", "HAS_UPGRADE_HIGH", "HAS_UPGRADE_LOW"]
    frames = [vam_output, sisa_bersih, sisa_terfilter] + list(hasil_pic.values())
    for i, d in enumerate(frames):
        frames[i] = d.drop(columns=kolom_bantu, errors="ignore")
    vam_output, sisa_bersih, sisa_terfilter = frames[:3]
    for pic, d in zip(hasil_pic.keys(), frames[3:]):
        hasil_pic[pic] = d

    def reorder(df):
        cols = df.columns.tolist()
        depan = [c for c in ["PIC", "WITEL", "NO_CONTACT", "NOHP", "nohp", "NCLI", "ncli"] if c in cols]
        return df[depan + [c for c in cols if c not in depan]]

    rekap_witel = df_terfilter["WITEL"].value_counts().reset_index()
    rekap_witel.columns = ["WITEL", "JUMLAH_DATA"]

    tmp_dir = zip_output_path.parent / (zip_output_path.stem + "_files")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    hasil_file = tmp_dir / "hasil_pembagian_vam_tam_ise.xlsx"
    sisa_file = tmp_dir / "sisa_data_belum_kepakai.xlsx"

    with pd.ExcelWriter(hasil_file, engine="openpyxl") as writer:
        reorder(vam_output).to_excel(writer, index=False, sheet_name="VAM")
        for pic, data in hasil_pic.items():
            reorder(data).to_excel(writer, index=False, sheet_name=pic[:31])
        rekap_witel.to_excel(writer, index=False, sheet_name="REKAP_AWAL_TERFILTER")

    with pd.ExcelWriter(sisa_file, engine="openpyxl") as writer:
        reorder(sisa_bersih).to_excel(writer, index=False, sheet_name="SISA_BERSIH")
        reorder(sisa_terfilter).to_excel(writer, index=False, sheet_name="SISA_TERFILTER")

    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(hasil_file, hasil_file.name)
        zf.write(sisa_file, sisa_file.name)

    return {"vam": int(len(vam_output)), "sisa_bersih": int(len(sisa_bersih)), "sisa_terfilter": int(len(sisa_terfilter)), "zip": zip_output_path.name}
