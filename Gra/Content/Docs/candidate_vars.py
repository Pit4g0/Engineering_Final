# candidate_vars.py -- generuje kandydatów na nazwy zmiennych (bez modyfikacji projektu)
import unreal, os, re, csv, traceback

OUT_DIR = r"C:\Users\USER\Desktop\inżynierka\Gra\Content\Docs\Candidates"
PACKAGE_PATHS = ["/Game"]
os.makedirs(OUT_DIR, exist_ok=True)

def L(m):
    try: unreal.log("[CAND] " + str(m))
    except: print("[CAND] " + str(m))

def sanitize(s):
    try: return str(s).strip()
    except: return ""

def tokenize(text):
    # prosta heurystyka: rozbij po nie-alfanum, zwróć unikalne tokeny długości >1
    toks = re.split(r'[^A-Za-z0-9_]+', str(text))
    res = []
    for t in toks:
        if len(t) > 1 and not t.isdigit():
            res.append(t)
    return res

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
# próbujemy ARFilter z TopLevelAssetPath, fallback jeśli nie zadziała
try:
    bp_class = unreal.TopLevelAssetPath("/Script/Engine.Blueprint")
    ar_filter = unreal.ARFilter(package_paths=PACKAGE_PATHS, class_paths=[bp_class], recursive_paths=True)
    assets = asset_registry.get_assets(ar_filter)
except Exception:
    assets = asset_registry.get_assets_by_path("/Game", True)

L("Znaleziono assetów: {}".format(len(assets)))

def collect_from_cdo(gen_class):
    res = set()
    if not gen_class:
        return res
    # spróbuj CDO
    try:
        get_def = getattr(gen_class, "get_default_object", None)
        if callable(get_def):
            cdo = get_def()
        else:
            cdo = None
    except Exception:
        cdo = None
    if not cdo:
        return res
    # zbieramy repry i tokenizujemy
    try:
        for a in dir(cdo):
            if a.startswith("_"):
                continue
            try:
                val = getattr(cdo, a)
            except Exception:
                continue
            # pomiń callables
            if callable(val):
                # ale tokenizuj nazwę atrybutu
                for tk in tokenize(a):
                    res.add(tk)
                continue
            # tokenizuj reprezentację wartości oraz nazwę atrybutu
            for tk in tokenize(a):
                res.add(tk)
            try:
                rep = repr(val)
                for tk in tokenize(rep)[:10]:
                    res.add(tk)
            except Exception:
                pass
    except Exception:
        pass
    return res

def collect_from_graphs(obj):
    found = set()
    try:
        # szukamy atrybutów, które mają .nodes
        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(obj, attr)
            except Exception:
                continue
            if isinstance(val, (list, tuple)) and val:
                first = val[0]
                if hasattr(first, "nodes"):
                    graphs = list(val)
                else:
                    graphs = []
            elif hasattr(val, "nodes"):
                graphs = [val]
            else:
                graphs = []
            for g in graphs:
                nodes = getattr(g, "nodes", []) or []
                for node in nodes:
                    try:
                        # sprawdź typowe pola
                        for field in ("variable_name","variable","member_name","member_reference","property_name","node_title","node_title_raw"):
                            if hasattr(node, field):
                                try:
                                    v = getattr(node, field)
                                    if v:
                                        # może być strukturą -> tokenizuj repr
                                        for tk in tokenize(v):
                                            found.add(tk)
                                except Exception:
                                    pass
                        # przeglądnij kilka atrybutów node
                        for a in dir(node)[:60]:
                            if a.startswith("_"):
                                continue
                            if any(k in a.lower() for k in ("var","variable","member","prop","name")):
                                try:
                                    val = getattr(node, a)
                                    for tk in tokenize(val):
                                        found.add(tk)
                                except Exception:
                                    pass
                    except Exception:
                        continue
    except Exception:
        pass
    return found

# Przejdź assety i zapisz CSV per-BP
for asset_data in assets:
    try:
        bp = None
        try:
            bp = asset_data.get_asset()
        except Exception:
            try:
                bp = unreal.EditorAssetLibrary.load_asset(str(getattr(asset_data, "package_name", "")))
            except Exception:
                bp = None
        if not bp or not isinstance(bp, unreal.Blueprint):
            continue

        pkg = str(getattr(asset_data, "package_name", "")) or ""
        name = bp.get_name()
        L("Scanning: " + name)

        # 1) gen_class
        gen_class = None
        try:
            if pkg:
                gen_class = unreal.EditorAssetLibrary.load_blueprint_class(pkg)
        except Exception:
            gen_class = None
        if not gen_class:
            try:
                if callable(getattr(bp, "get_generated_class", None)):
                    gen_class = bp.get_generated_class()
                else:
                    gen_class = getattr(bp, "generated_class", None)
            except Exception:
                gen_class = None

        cand = set()

        # a) z CDO
        cand.update(collect_from_cdo(gen_class))

        # b) z grafów
        cand.update(collect_from_graphs(bp))
        if gen_class:
            cand.update(collect_from_graphs(gen_class))

        # c) jeśli gen_class ma jakieś properties/funkcje -> tokenizuj ich nazwy
        try:
            if gen_class:
                # get_properties/get_functions mogą nie istnieć
                if callable(getattr(gen_class, "get_properties", None)):
                    for p in gen_class.get_properties():
                        try:
                            nm = getattr(p, "get_name", lambda: str(p))()
                            for tk in tokenize(nm):
                                cand.add(tk)
                        except Exception:
                            continue
                elif getattr(gen_class, "properties", None):
                    for p in getattr(gen_class, "properties", []):
                        try:
                            nm = getattr(p, "get_name", lambda: str(p))()
                            for tk in tokenize(nm):
                                cand.add(tk)
                        except Exception:
                            continue
        except Exception:
            pass

        # d) heurystyka na nazwie BP i ścieżce
        cand.add(name)
        for tk in tokenize(pkg):
            cand.add(tk)

        # zapisz CSV (kolumny: candidate, source hints)
        out_csv = os.path.join(OUT_DIR, f"{name}_candidates.csv")
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["candidate"])
            for c in sorted(cand):
                w.writerow([c])
        L(f"Wrote candidates for {name} -> {out_csv} ({len(cand)} items)")

    except Exception as e:
        unreal.log_warning(traceback.format_exc())
        continue

L("Done.")
