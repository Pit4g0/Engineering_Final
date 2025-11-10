# inspect_tags_and_cdo.py
import unreal, os, traceback

OUT = r"C:\Users\USER\Desktop\inżynierka\Gra\Content\Docs\debug_tags"
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    "/Game/Core/Player/BP_Player_Character",
    "/Game/Core/BP_Game_Mode",
    "/Game/Levels_Related/BP_Switch_Sublevels"
]  # możesz dopisać inne ścieżki które widziałeś w debug

def L(s):
    try:
        unreal.log("[INSPECT] " + str(s))
    except Exception:
        print("[INSPECT] " + str(s))

def safe_str(x):
    try:
        return repr(x)
    except Exception:
        return "<unrepr>"

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

for pkg in TARGETS:
    try:
        L("=== Inspecting package: " + pkg)
        # znajdź AssetData dla package
        ad_list = asset_registry.get_assets_by_path(pkg, False)
        if not ad_list:
            # spróbuj get_assets_by_package_name (nie zawsze istnieje)
            try:
                ad = asset_registry.get_asset_by_object_path(pkg + "." + pkg.split("/")[-1])
                ad_list = [ad] if ad else []
            except Exception:
                ad_list = []
        if not ad_list:
            L("No AssetData found for: " + pkg)
            continue

        for ad in ad_list:
            try:
                name = str(getattr(ad, "asset_name", getattr(ad, "asset_name", "<no name>")))
                outfile = os.path.join(OUT, f"{name}_tags_debug.txt")
                lines = []
                lines.append("AssetData repr: " + safe_str(ad))
                # dir(asset_data) sample
                try:
                    lines.append("\n--- dir(asset_data) sample ---")
                    lines.append(", ".join([a for a in dir(ad)[:80]]))
                except Exception:
                    lines.append("dir(asset_data) failed")

                # tags and values (if available)
                try:
                    tav = getattr(ad, "tags_and_values", None)
                    if tav:
                        lines.append("\n--- tags_and_values (dict-like) ---")
                        try:
                            # iterate
                            for k, v in tav.items():
                                lines.append(f"{k} : {v}")
                        except Exception:
                            lines.append("Could not iterate tags_and_values normally, repr:")
                            lines.append(repr(tav))
                    else:
                        lines.append("\n--- tags_and_values: None ---")
                except Exception:
                    lines.append("\n--- error reading tags_and_values ---")
                    lines.append(traceback.format_exc())

                # try ad.get_tag_value(key) for common keys
                try:
                    common_keys = ["BlueprintVariables", "VariableDescriptions", "BlueprintDescription", "NativeParentClass"]
                    lines.append("\n--- trying get_tag_value for common keys ---")
                    for k in common_keys:
                        try:
                            val = None
                            if callable(getattr(ad, "get_tag_value", None)):
                                val = ad.get_tag_value(k)
                            else:
                                # fallback: maybe tags property exists
                                tags = getattr(ad, "tags", None)
                                val = getattr(tags, k, None) if tags else None
                            lines.append(f"tag[{k}] -> {safe_str(val)}")
                        except Exception:
                            lines.append(f"tag[{k}] -> error")
                except Exception:
                    lines.append("error in tag value checks")

                # load asset object (bp) if possible
                bp = None
                try:
                    bp = ad.get_asset()
                except Exception:
                    try:
                        bp = unreal.EditorAssetLibrary.load_asset(str(getattr(ad, "package_name", "")))
                    except Exception:
                        bp = None

                if not bp:
                    lines.append("\n--- bp object: NOT LOADED ---")
                else:
                    lines.append("\n--- bp object repr/type ---")
                    try:
                        lines.append("type(bp): " + safe_str(type(bp)))
                    except:
                        pass
                    try:
                        lines.append("dir(bp) sample: " + ", ".join([a for a in dir(bp)[:80]]))
                    except:
                        pass
                    # check availability of common attrs
                    checks = ["new_variables","generated_class","get_generated_class","simple_construction_script","ubergraph_pages","blueprint_description"]
                    for c in checks:
                        lines.append(f"hasattr(bp, '{c}') = {hasattr(bp, c)}")
                    # if blueprint_description exists read it
                    if hasattr(bp, "blueprint_description"):
                        try:
                            lines.append("blueprint_description = " + safe_str(getattr(bp, "blueprint_description")))
                        except:
                            lines.append("blueprint_description read error")

                # attempt to get gen_class
                gen = None
                try:
                    pkgname = str(getattr(ad, "package_name", "") or "")
                    if pkgname:
                        try:
                            gen = unreal.EditorAssetLibrary.load_blueprint_class(pkgname)
                            lines.append("\nLoaded gen_class via load_blueprint_class: " + safe_str(gen))
                        except Exception:
                            gen = None
                except Exception:
                    gen = None
                if not gen and bp:
                    try:
                        if callable(getattr(bp, "get_generated_class", None)):
                            gen = bp.get_generated_class()
                            lines.append("Loaded gen_class via bp.get_generated_class(): " + safe_str(gen))
                        else:
                            gen = getattr(bp, "generated_class", None)
                            lines.append("Loaded gen_class via bp.generated_class: " + safe_str(gen))
                    except Exception:
                        gen = None

                if gen:
                    try:
                        lines.append("\n--- gen_class dir sample ---")
                        lines.append(", ".join([a for a in dir(gen)[:120]]))
                    except:
                        pass
                    # try get_default_object
                    try:
                        getdef = getattr(gen, "get_default_object", None)
                        if callable(getdef):
                            cdo = getdef()
                            lines.append("\nCDO type: " + safe_str(type(cdo)))
                            # show dir(cdo) sample
                            try:
                                lines.append("dir(CDO) sample: " + ", ".join([a for a in dir(cdo)[:120]]))
                            except:
                                pass
                            # try to repr some attr names
                            sample_attrs = []
                            try:
                                for a in dir(cdo)[:200]:
                                    if a.startswith("_"):
                                        continue
                                    try:
                                        v = getattr(cdo, a)
                                        sample_attrs.append(f"{a} => {safe_str(v)}")
                                    except Exception:
                                        sample_attrs.append(f"{a} => <err>")
                                    if len(sample_attrs) > 80:
                                        break
                                lines.append("\nCDO attribute repr sample:")
                                lines.extend(sample_attrs[:80])
                            except Exception:
                                lines.append("Error enumerating CDO attributes")
                        else:
                            lines.append("\ngen_class has no get_default_object callable")
                    except Exception:
                        lines.append("\nError getting CDO: " + traceback.format_exc())
                else:
                    lines.append("\nNo gen_class obtained")

                # write file
                try:
                    with open(outfile, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines))
                    L("Wrote: " + outfile)
                except Exception:
                    L("Failed to write file: " + outfile)
            except Exception as e:
                L("Inner error for asset_data: " + str(e))
                unreal.log_warning(traceback.format_exc())

    except Exception as e:
        L("Error top loop: " + str(e))
        unreal.log_warning(traceback.format_exc())

L("Done inspect tags and cdo. Check folder: " + OUT)
