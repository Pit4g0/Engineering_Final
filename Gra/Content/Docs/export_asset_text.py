# export_asset_text.py
import unreal, os, re, collections

# ---- CONFIG ----
OUT_DIR = r"C:\Users\USER\Desktop\inżynierka\Gra\Content\Docs\export_text"
os.makedirs(OUT_DIR, exist_ok=True)

# Lista assetów które chcesz zbadać (pełna package path bez .uasset)
TARGET_PACKAGES = [
    "/Game/Core/Player/BP_Player_Character",
    "/Game/Core/BP_Game_Mode",
    "/Game/Levels_Related/BP_Switch_Sublevels"
]
# Jeśli chcesz przebadać wszystkie BP w /Game, ustaw TARGET_PACKAGES = [] i poniżej użyj get_assets_by_path

# ---- Helpers ----
def L(m):
    try:
        unreal.log("[EXPORT_TEXT] " + str(m))
    except:
        print("[EXPORT_TEXT] " + str(m))

def tokenize(text):
    # zwraca tokeny alfanumeryczne min. długość 2
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", text)
    return toks

# ---- Asset selection ----
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = []
if TARGET_PACKAGES:
    for pkg in TARGET_PACKAGES:
        # get assets under the exact package path
        found = asset_registry.get_assets_by_path(pkg, False)
        if found:
            assets.extend(found)
        else:
            # fallback: try to find by package name object path
            try:
                ad = asset_registry.get_asset_by_object_path(pkg + "." + pkg.split("/")[-1])
                if ad:
                    assets.append(ad)
            except Exception:
                pass
else:
    # przebadaj wszystko w /Game
    assets = asset_registry.get_assets_by_path("/Game", True)

L("Znaleziono assetów do zbadania: {}".format(len(assets)))

# ---- Process each asset_data ----
for ad in assets:
    try:
        pkg_name = str(getattr(ad, "package_name", "") or "")
        asset_name = str(getattr(ad, "asset_name", "") or "")
        out_base = os.path.join(OUT_DIR, "{}_{}".format(asset_name, pkg_name.strip("/").replace("/","_")))
        L("Przetwarzam: {}  ({})".format(asset_name, pkg_name))

        # 1) zapis export_text (jeśli dostępny)
        txt = None
        try:
            # AssetData ma metodę export_text -> zwraca string z serializacją
            if callable(getattr(ad, "export_text", None)):
                txt = ad.export_text()
            else:
                # fallback: spróbuj pobrać asset i użyć EditorAssetLibrary.export_text (rzadko dostępne)
                try:
                    asset_obj = ad.get_asset()
                    if asset_obj and callable(getattr(asset_obj, "export_text", None)):
                        txt = asset_obj.export_text()
                except Exception:
                    txt = None
        except Exception:
            txt = None

        if not txt:
            L("  Brak export_text dla: {}".format(asset_name))
            # nadal zapisz minimalny raport
            with open(out_base + "_export.txt", "w", encoding="utf-8") as f:
                f.write("NO export_text available for asset.\nAssetData repr: {}\n".format(repr(ad)))
            continue

        # zapisz pełny export
        with open(out_base + "_export.txt", "w", encoding="utf-8") as f:
            f.write(txt)

        # 2) prosta analiza tokenów: policz najczęstsze tokeny w tekście
        toks = tokenize(txt)
        # odfiltruj zwykłe angielskie słowa i typowe nazwy metod które widzieliśmy (opcjonalne)
        stopwords = set(["Blueprint","Class","True","False","Default","Name","None","Object","Struct","Function"])
        toks_filtered = [t for t in toks if len(t) > 2 and t not in stopwords and not t.isdigit()]
        freq = collections.Counter(toks_filtered)
        most = freq.most_common(200)

        # zapisz listę kandydatów (najczęstsze tokeny)
        with open(out_base + "_candidates.txt", "w", encoding="utf-8") as f:
            f.write("Top tokens (candidate variable/property names) for asset {} (package {}):\n\n".format(asset_name, pkg_name))
            for tok,ct in most:
                f.write(f"{ct:6d}  {tok}\n")

        L("  Zapisano export_text i candidates dla: {}".format(asset_name))

    except Exception as e:
        L("  ERROR przy przetwarzaniu {}: {}".format(getattr(ad, "package_name", ad), e))

L("Gotowe. Sprawdź folder: {}".format(OUT_DIR))
