"""
translate_all_locales.py
Traduzione globale e completa dei cataloghi Frontend (app/static/locales/)
e Backend (app/i18n_locales/) per le 7 lingue europee:
  de (Tedesco), es (Spagnolo), fr (Francese), nl (Olandese),
  pl (Polacco), pt (Portoghese), el (Greco).
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TARGET_LANGS = ["de", "es", "fr", "nl", "pl", "pt", "el"]

def extract_placeholders(text: str):
    return re.findall(r"\{[a-zA-Z0-9_]+\}", text)

def translate_single(text: str, target_lang: str) -> str:
    if not text or not isinstance(text, str) or not text.strip():
        return text
    
    phs = extract_placeholders(text)
    temp = text
    for i, ph in enumerate(phs):
        temp = temp.replace(ph, f"__PH_{i}__", 1)
        
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(temp)}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join([part[0] for part in data[0] if part[0]])
            
            for i, ph in enumerate(phs):
                translated = re.sub(rf"__\s*ph_{i}\s*__", ph, translated, flags=re.IGNORECASE)
                
            # Validazione placeholder: se sono andati persi, ripristina
            orig_set = set(re.findall(r"\{(\w+)\}", text))
            trans_set = set(re.findall(r"\{(\w+)\}", translated))
            if orig_set != trans_set:
                # Ripristina placeholders mancanti alla fine se necessario
                missing = orig_set - trans_set
                for m in missing:
                    translated += f" {{{m}}}"
            return translated
        except Exception as e:
            time.sleep(1)
            if attempt == 2:
                print(f"Warning: translation failed for '{text[:30]}...': {e}")
                return text

def translate_batch(texts: list, target_lang: str) -> list:
    if not texts:
        return []
    
    delimiter = " ||| "
    all_phs = []
    processed = []
    for t in texts:
        phs = extract_placeholders(t)
        all_phs.append(phs)
        temp = t
        for i, ph in enumerate(phs):
            temp = temp.replace(ph, f"__PH_{i}__", 1)
        processed.append(temp)
        
    combined = delimiter.join(processed)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(combined)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        translated_combined = "".join([part[0] for part in data[0] if part[0]])
        parts = re.split(r"\s*\|\|\|\s*", translated_combined)
        
        if len(parts) == len(texts):
            results = []
            for part, phs, orig in zip(parts, all_phs, texts):
                for i, ph in enumerate(phs):
                    part = re.sub(rf"__\s*ph_{i}\s*__", ph, part, flags=re.IGNORECASE)
                
                orig_set = set(re.findall(r"\{(\w+)\}", orig))
                trans_set = set(re.findall(r"\{(\w+)\}", part))
                if orig_set != trans_set:
                    part = translate_single(orig, target_lang)
                results.append(part)
            return results
    except Exception:
        pass
    
    # Fallback item-by-item
    return [translate_single(t, target_lang) for t in texts]

def flatten_dict(d, prefix=""):
    items = {}
    for k, v in d.items():
        if isinstance(v, dict):
            items.update(flatten_dict(v, f"{prefix}{k}."))
        else:
            items[f"{prefix}{k}"] = v
    return items

def unflatten_dict(flat_dict):
    result = {}
    for compound_key, val in flat_dict.items():
        keys = compound_key.split(".")
        curr = result
        for k in keys[:-1]:
            curr = curr.setdefault(k, {})
        curr[keys[-1]] = val
    return result

def translate_catalog(en_data, target_lang, is_frontend=True):
    flat_en = flatten_dict(en_data)
    
    keys = list(flat_en.keys())
    values = [flat_en[k] for k in keys]
    
    # Isola i valori stringa da tradurre
    str_indices = [i for i, v in enumerate(values) if isinstance(v, str) and v.strip()]
    str_texts = [values[i] for i in str_indices]
    
    translated_strs = []
    chunk_size = 20
    for c in range(0, len(str_texts), chunk_size):
        chunk = str_texts[c:c+chunk_size]
        res = translate_batch(chunk, target_lang)
        translated_strs.extend(res)
        time.sleep(0.1) # Breve pausa per evitare rate limit
        
    final_values = list(values)
    for idx, trans in zip(str_indices, translated_strs):
        # Verifica finale placeholder
        orig = values[idx]
        orig_phs = set(re.findall(r"\{(\w+)\}", orig))
        trans_phs = set(re.findall(r"\{(\w+)\}", trans))
        if orig_phs != trans_phs:
            trans = translate_single(orig, target_lang)
        final_values[idx] = trans
        
    flat_translated = {k: v for k, v in zip(keys, final_values)}
    return unflatten_dict(flat_translated)

def process_frontend():
    print("\n🌐 [1/2] Traduzione globale cataloghi FRONTEND (app/static/locales/)...")
    en_path = Path("app/static/locales/en.json")
    en_data = json.loads(en_path.read_text(encoding="utf-8"))
    
    for lang in TARGET_LANGS:
        print(f"  -> Traduzione in corso per: {lang.upper()}...")
        trans_data = translate_catalog(en_data, lang, is_frontend=True)
        out_path = Path(f"app/static/locales/{lang}.json")
        out_path.write_text(json.dumps(trans_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  ✅ {lang.upper()} completato ({len(flatten_dict(trans_data))} chiavi)")

def process_backend():
    print("\n📦 [2/2] Traduzione globale cataloghi BACKEND (app/i18n_locales/)...")
    be_en_dir = Path("app/i18n_locales/en")
    files = sorted(list(be_en_dir.glob("*.json")))
    
    for lang in TARGET_LANGS:
        print(f"  -> Traduzione backend per: {lang.upper()}...")
        target_dir = Path(f"app/i18n_locales/{lang}")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for f in files:
            en_data = json.loads(f.read_text(encoding="utf-8"))
            trans_data = translate_catalog(en_data, lang, is_frontend=False)
            out_file = target_dir / f.name
            out_file.write_text(json.dumps(trans_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  ✅ Backend {lang.upper()} completato ({len(files)} file)")

if __name__ == "__main__":
    start = time.time()
    process_frontend()
    process_backend()
    print(f"\n🎉 Traduzione globale completata in {time.time() - start:.1f} secondi!")

