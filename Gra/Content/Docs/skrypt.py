# debug_bp_inspect.py
import unreal, os, traceback

OUT_DIR = r"C:\Users\USER\Desktop\inżynierka\Gra\Content\Docs\debug"
os.makedirs(OUT_DIR, exist_ok=True)

MAX_TO_INSPECT = 20  # ile BP przebadać (zmień jeśli trzeba)
PACKAGE_PATH = "/Game"

def L(s):
    try:
        unreal.log("[BP_DEBUG] " + str(s))
    except Exception:
        print("[BP_DEBUG] " + str(s))

def safe_str(x):
    try:
        return str(x)
    except Exception:
        return "<unprintable>"

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = asset_registry.get_assets_by_path(PACKAGE_PATH, True)
L(f"Znaleziono assetów w {PACKAGE_PATH}: {len(all_assets)} (będę szukać Blueprintów, max {MAX_TO_INSPECT})")

inspected = 0
for asset_data in all_assets:
    if inspected >= MAX_TO_INSPECT:
        break
    try:
        # spróbuj załadować asset
        bp = None
        try:
            bp = asset_data.get_asset()
        except Exception:
            try:
                pkg = str(getattr(asset_data, "package_name", "") or "")
                if pkg:
                    bp = unreal.EditorAssetLibrary.load_asset(pkg)
            except Exception:
                bp = None

        if not bp:
            continue

        # sprawdź typ
        is_bp = isinstance(bp, unreal.Blueprint)
        if not is_bp:
            continue

        inspected += 1
        bp_name = bp.get_name()
        pkg_name = str(getattr(asset_data, "package_name", asset_data))
        L(f"=== INSPECT [{inspected}] {bp_name}  ({pkg_name}) ===")

        debug_lines = []
        debug_lines.append(f"Inspecting: {bp_name}")
        debug_lines.append(f"Package: {pkg_name}")
        debug_lines.append("")

        # 1) top-level info about bp object
        try:
            debug_lines.append("BP object type: " + safe_str(type(bp)))
            attrs = [a for a in dir(bp) if not a.startswith("_")]
            debug_lines.append("Top attributes (sample): " + ", ".join(attrs[:40]))
        except Exception:
            debug_lines.append("Cannot list bp dir()")

        # 2) check common attributes / methods existence
        checks = [
            "new_variables",
            "generated_class",
            "get_generated_class",
            "simple_construction_script",
            "ubergraph_pages",
            "blueprint_description",
            "get_asset",
            "get_name"
        ]
        for c in checks:
            debug_lines.append(f"hasattr(bp, '{c}') = {hasattr(bp, c)}")

        # 3) dump bp.new_variables if present
        try:
            nv = getattr(bp, "new_variables", None)
            if nv:
                debug_lines.append(f"\nnew_variables count: {len(nv)}")
                for i, v in enumerate(nv[:50]):
                    try:
                        debug_lines.append(f"  [{i}] var_name={getattr(v,'var_name',None)}  var_type={getattr(v,'var_type',None)} tooltip={getattr(v,'tooltip',None)} category={getattr(v,'category',None)} is_editable={getattr(v,'is_editable',None)} replication={getattr(v,'replication',None)}")
                    except Exception:
                        debug_lines.append(f"  [{i}] (error reading variable descriptor)")
            else:
                debug_lines.append("\nnew_variables: None or empty")
        except Exception:
            debug_lines.append("\nException when reading new_variables:\n" + traceback.format_exc())

        # 4) try to get generated class using multiple ways
        gen_class = None
        try:
            # first try EditorAssetLibrary.load_blueprint_class(pkg)
            try:
                gen_class = unreal.EditorAssetLibrary.load_blueprint_class(pkg_name)
                debug_lines.append(f"\nLoaded gen_class via load_blueprint_class: {safe_str(gen_class)}")
            except Exception:
                gen_class = None
            # fallback to bp.get_generated_class()
            if not gen_class and callable(getattr(bp, "get_generated_class", None)):
                try:
                    gen_class = bp.get_generated_class()
                    debug_lines.append(f"Loaded gen_class via bp.get_generated_class(): {safe_str(gen_class)}")
                except Exception:
                    gen_class = None
            # fallback to attribute
            if not gen_class and hasattr(bp, "generated_class"):
                try:
                    gen_class = getattr(bp, "generated_class", None)
                    debug_lines.append(f"gen_class via bp.generated_class: {safe_str(gen_class)}")
                except Exception:
                    gen_class = None
        except Exception:
            debug_lines.append("Exception while obtaining generated class:\n" + traceback.format_exc())

        # 5) dump gen_class info if present
        if gen_class:
            try:
                debug_lines.append("\n--- generated class info ---")
                debug_lines.append("type: " + safe_str(type(gen_class)))
                # try common props
                for a in ("super_class", "get_super_class", "get_functions", "get_properties", "functions", "properties", "get_default_object", "get_name"):
                    debug_lines.append(f"hasattr(gen_class, '{a}') = {hasattr(gen_class, a)}")
                # try get_functions
                try:
                    gf = getattr(gen_class, "get_functions", None)
                    if callable(gf):
                        fs = gen_class.get_functions()
                        debug_lines.append(f"gen_class.get_functions() count: {len(fs)}")
                        for f in fs[:20]:
                            try:
                                debug_lines.append("  func: " + safe_str(getattr(f, "get_name", lambda: f)()))
                            except Exception:
                                debug_lines.append("  func: <error>")
                    else:
                        debug_lines.append("gen_class.get_functions not callable")
                except Exception:
                    debug_lines.append("Exception while listing gen_class.get_functions():\n" + traceback.format_exc())

                # try get_properties
                try:
                    gp = getattr(gen_class, "get_properties", None)
                    if callable(gp):
                        ps = gen_class.get_properties()
                        debug_lines.append(f"gen_class.get_properties() count: {len(ps)}")
                        for p in ps[:40]:
                            try:
                                name = getattr(p, "get_name", lambda: str(p))()
                                debug_lines.append(f"  prop: {safe_str(name)}")
                            except Exception:
                                debug_lines.append("  prop: <error>")
                    else:
                        debug_lines.append("gen_class.get_properties not callable")
                except Exception:
                    debug_lines.append("Exception while listing gen_class.get_properties():\n" + traceback.format_exc())
            except Exception:
                debug_lines.append("Exception while dumping gen_class:\n" + traceback.format_exc())
        else:
            debug_lines.append("\nNo generated_class found by any method.")

        # 6) try default object (CDO)
        try:
            cdo = None
            if gen_class and callable(getattr(gen_class, "get_default_object", None)):
                try:
                    cdo = gen_class.get_default_object()
                    debug_lines.append(f"\nCDO obtained from gen_class.get_default_object(): {safe_str(type(cdo))}")
                except Exception:
                    cdo = None
            if not cdo:
                debug_lines.append("CDO: not obtained")
            else:
                # list some attrs of CDO
                attrs = [a for a in dir(cdo) if not a.startswith("_")]
                debug_lines.append(f"CDO attrs sample (first 60): {attrs[:60]}")
                # try to pick out obvious variables by name heuristics
                potential_vars = [a for a in attrs if any(x in a.lower() for x in ("health","speed","name","max","min","count","is","b","num","id","time"))][:60]
                debug_lines.append(f"CDO heuristics sample: {potential_vars}")
        except Exception:
            debug_lines.append("Exception while obtaining/inspecting CDO:\n" + traceback.format_exc())

        # 7) examine ubergraph_pages and nodes: show counts and one node repr
        try:
            ugs = getattr(bp, "ubergraph_pages", None)
            if ugs:
                debug_lines.append(f"\nubergraph_pages count: {len(ugs)}")
                for gi, g in enumerate(ugs[:5]):
                    try:
                        nodes = getattr(g, "nodes", []) or []
                        debug_lines.append(f" graph[{gi}] nodes count: {len(nodes)}")
                        for ni, node in enumerate(nodes[:6]):
                            try:
                                debug_lines.append(f"  node[{ni}] class: {node.get_class().get_name()} repr: {safe_str(node)}")
                                # show some node attrs that might refer to variables
                                for attr in ("variable_name","variable","member_name","node_title","node_title_raw"):
                                    if hasattr(node, attr):
                                        try:
                                            debug_lines.append(f"    attr {attr}: {getattr(node, attr)}")
                                        except:
                                            pass
                                # show first 8 attributes of node
                                node_attrs = [a for a in dir(node) if not a.startswith("_")][:8]
                                debug_lines.append(f"    node attrs sample: {node_attrs}")
                            except Exception:
                                debug_lines.append("  node read error")
                    except Exception:
                        debug_lines.append(" graph read error")
            else:
                debug_lines.append("\nNo ubergraph_pages found or empty")
        except Exception:
            debug_lines.append("\nException inspecting ubergraph_pages:\n" + traceback.format_exc())

        # write debug file
        fname = os.path.join(OUT_DIR, f"{bp_name}_debug.txt")
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write("\n".join(debug_lines))
            L(f"Wrote debug file: {fname}")
        except Exception:
            L("Failed to write debug file: " + safe_str(fname))

    except Exception as e:
        L("Error inspecting asset: " + safe_str(getattr(asset_data, "package_name", asset_data)))
        unreal.log_warning(traceback.format_exc())
        continue

L("Done inspection.")
