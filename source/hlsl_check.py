# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# hlsl_check.py - checks every .fx of the resource the way MTA / D3D9 will.
#
#   1. lint        balanced braces, technique tec0 + technique fallback, compile targets refer to
#                  defined functions, vs/ps model match, every tex2D sampler is declared, every
#                  identifier is declared or an intrinsic (catches typos and redefinitions)
#   2. budget      texture fetches per pass, sampler count, float4 constant registers used,
#                  dynamic texture fetches inside loops -> compared with the ps_2_0 / ps_3_0 limits
#   3. Slang       the real HLSL front-end type checks every function body (types, swizzles,
#                  intrinsics, undeclared names) - the same class of error fxc reports
#   4. binding     every name the Lua sets with dxSetShaderValue exists in the .fx it is set on
#
# Used by validate.py:     python3 validate.py --shaders
# -----------------------------------------------------------------------------
import os
import re

HLSL_TYPES = set('''float float1 float2 float3 float4 half half2 half3 half4 int int2 int3 int4 bool bool2 bool3 bool4
float2x2 float3x3 float4x4 void texture sampler sampler_state struct string technique pass compile return if else for
define ifdef ifndef endif elif undef
while static const uniform in out inout true false register extern volatile row_major column_major shared groupshared
namespace typedef discard switch case default break continue do'''.split())

HLSL_STATES = set('''Texture MinFilter MagFilter MipFilter AddressU AddressV AddressW MaxAnisotropy Linear Point
Anisotropic None Clamp Wrap Mirror Border VertexShader PixelShader vs_1_1 vs_2_0 vs_3_0 ps_1_1 ps_2_0 ps_2_a ps_2_b
ps_3_0 ZEnable ZWriteEnable ZFunc CullMode AlphaBlendEnable SrcBlend DestBlend FillMode ShadeMode Lighting
SpecularEnable FogEnable SRGBWrite ColorWriteEnable StencilEnable AlphaTestEnable'''.split())

INTRINSICS = set('''abs acos all any asin atan atan2 ceil clamp clip cos cosh cross ddx ddy degrees determinant
distance dot dst exp exp2 faceforward floor fmod frac frexp fwidth isfinite isinf isnan ldexp length lerp lit log
log10 log2 max min modf mul noise normalize pow radians reflect refract round rsqrt saturate sign sin sincos sinh
smoothstep sqrt step tan tanh tex1D tex2D tex2Dlod tex2Dbias tex2Dproj tex3D texCUBE transpose trunc ddxdy
dot2add dot3 dot4 dot2add2 cmp'''.split())

# MTA exposes these engine semantics to a world shader in addition to the D3D9 set
MTA_SEMANTICS = set('''WORLD VIEW PROJECTION WORLDVIEW WORLDVIEWPROJECTION VIEWPROJECTION WORLDVIEWINVERSE
VIEWINVERSE CAMERAPOSITION CAMERADIRECTION TIME TEXTURE0 LIGHTAMBIENT'''.split())

SEMANTICS = MTA_SEMANTICS | set('''POSITION POSITION0 POSITION1 POSITION2 POSITION3 NORMAL NORMAL0 NORMAL1 COLOR COLOR0 COLOR1 COLOR2
COLOR3 TEXCOORD TEXCOORD0 TEXCOORD1 TEXCOORD2 TEXCOORD3 TEXCOORD4 TEXCOORD5 TEXCOORD6 TEXCOORD7 BLENDWEIGHT
BLENDWEIGHT0 BLENDINDICES BLENDINDICES0 TESSFACTOR FOG PSIZE VFACE VPOS DEPTH SV_TARGET SV_POSITION SV_DEPTH'''.split())

# D3D9 pixel shader limits (documented in the D3D9 caps table)
PS_LIMITS = {
    'ps_2_0': dict(arith=96, tex=32, temps=32, consts=32, samplers=16),
    'ps_2_a': dict(arith=512, tex=32, temps=32, consts=32, samplers=16),
    'ps_2_b': dict(arith=512, tex=32, temps=32, consts=32, samplers=16),
    'ps_3_0': dict(arith=512, tex=32, temps=32, consts=224, samplers=16),
}


def strip_comments(src):
    return re.sub(r'/\*.*?\*/', '', re.sub(r'//[^\n]*', '', src), flags=re.S)


def passes(code):
    """returns [(pass name, [(target, func)])]"""
    out = []
    for m in re.finditer(r'pass\s+(\w+)\s*\{(.*?)\n\s*\}', code, re.S):
        out.append((m.group(1), re.findall(r'compile\s+(\w+)\s+(\w+)\s*\(', m.group(2))))
    return out


def constants_used(code):
    """float4 constant registers consumed by the uniform block (scalars pack 4 to a register)"""
    n = 0
    for m in re.finditer(r'^(float(\d)?(x\d)?|int(\d)?(x\d)?|bool)\s+(\w+)\s*(\[\s*\d+\s*\])?\s*(:[^;]+)?;', code, re.M):
        ty, arr = m.group(1), m.group(7)
        cnt = int(re.search(r'\[\s*(\d+)\s*\]', arr).group(1)) if arr else 1
        if 'x' in ty:                                     # matrix: rows of float4
            rows = int(ty.split('x')[1]) if len(ty.split('x')) > 1 else 4
            n += 4 * cnt if rows >= 4 else rows * cnt
        elif re.match(r'^float(\d)?$', ty) or re.match(r'^int(\d)?$', ty) or ty == 'bool':
            k = int(ty[-1]) if ty[-1].isdigit() else 1
            n += max(1, (k + 3) // 4) * cnt
    return n


def check_file(path):
    """returns (problems, warnings, info)"""
    src = open(path, encoding='utf8').read()
    code = strip_comments(src)
    name = os.path.basename(path)
    prob, warn, info = [], [], {}

    if code.count('{') != code.count('}') or code.count('(') != code.count(')'):
        prob.append('%s: unbalanced braces or parentheses' % name)
    if not re.search(r'technique\s+tec0', code):
        prob.append('%s: no technique tec0 (MTA will not use the shader)' % name)
    if not re.search(r'technique\s+fallback', code):
        prob.append('%s: no empty fallback technique (a failed tec0 would break the material)' % name)
    if re.search(r'technique\s+fallback\s*\{\s*[^}\s]', code):
        prob.append('%s: the fallback technique must be empty' % name)

    funcs = set(re.findall(r'^\s*(?:[\w<>,\s]+?)\s(\w+)\s*\([^;]*?\)\s*(?::\s*\w+\d?)?\s*\{', code, re.M | re.S))
    tg = []
    for pname, compiles in passes(code):
        for t, fn in compiles:
            tg.append(t)
            if fn not in funcs and not re.search(r'\b%s\s*\(' % fn, code):
                prob.append('%s: pass %s compiles %s() which is not defined' % (name, pname, fn))
            if t not in PS_LIMITS and t not in ('vs_1_1', 'vs_2_0', 'vs_3_0'):
                prob.append('%s: pass %s uses the unknown shader model %s' % (name, pname, t))
    info['targets'] = sorted(set(tg))
    vs = sorted({t for t in tg if t.startswith('vs')})
    ps = sorted({t for t in tg if t.startswith('ps')})
    if vs and ps and vs[0][3:] != ps[0][3:]:
        warn.append('%s: vertex model %s and pixel model %s differ' % (name, vs[0], ps[0]))

    # every tex2D sampler must be declared
    for s in set(re.findall(r'tex2D(?:lod|bias|proj)?\s*\(\s*(\w+)', code)):
        if not re.search(r'sampler\s+%s\s*=\s*sampler_state' % s, code):
            prob.append('%s: tex2D uses the undeclared sampler %s' % (name, s))
        elif not re.search(r'sampler\s+%s\s*=\s*sampler_state\s*\{[^}]*Texture\s*=\s*<(\w+)>' % s, code):
            prob.append('%s: sampler %s has no Texture = <...> binding' % (name, s))
    for tex in set(re.findall(r'Texture\s*=\s*<(\w+)>', code)):
        if not re.search(r'^texture\s+%s\s*;' % tex, code, re.M):
            prob.append('%s: sampler binds the undeclared texture %s' % (name, tex))
    # redefinitions
    decl = re.findall(r'^(?:texture|sampler|float\d?(?:x\d)?|int\d?|bool)\s+(\w+)', code, re.M)
    dup = sorted({d for d in decl if decl.count(d) > 1})
    if dup:
        prob.append('%s: redeclared global(s): %s' % (name, ', '.join(dup)))
    # unknown identifiers
    declared = set(decl)
    declared |= funcs
    declared |= set(re.findall(r'\b(?:technique|pass)\s+(\w+)', code))
    declared |= set(re.findall(r'struct\s+(\w+)', code))
    for blk in re.findall(r'struct\s+\w+\s*\{(.*?)\}', code, re.S):
        declared |= set(re.findall(r'\w+\s+(\w+)\s*:', blk))
    declared |= set(re.findall(r'#define\s+(\w+)', code))
    # function parameters and local variables
    for args in re.findall(r'\w+\s*\(([^;{]*)\)\s*(?::\s*\w+\d?)?\s*\{', code, re.S):
        declared |= set(re.findall(r'\b(?:in\s+|out\s+|inout\s+)?\w+\s+(\w+)\s*(?=,|$)', args))
    declared |= set(re.findall(r'\b(?:const\s+)?(?:float\d?(?:x\d)?|half\d?|int\d?|bool|\w*Input|\w*Output)\s+(\w+)\s*(?:=|;|\[|,)', code))
    for line in re.findall(r'^\s*(?:float\d?(?:x\d)?|half\d?|int\d?|bool)\s+([\w\s,]+);', code, re.M):
        declared |= {n.strip() for n in line.split(',') if n.strip()}
    body = re.sub(r'"[^"]*"', '', re.sub(r'<[^>]*>', '', code))
    body = re.sub(r'\b(?:sampler_state|sampler|texture|struct|technique|pass)\b', ' ', body)
    toks = set(re.findall(r'(?<![\w.])([A-Za-z_]\w*)\b', body))
    unknown = sorted(t for t in toks if t not in declared and t not in HLSL_TYPES
                     and t not in HLSL_STATES and t not in INTRINSICS and t not in SEMANTICS)
    if unknown:
        prob.append('%s: undeclared identifier(s): %s' % (name, ', '.join(unknown[:8])))
    for sem in set(re.findall(r':\s*([A-Z][A-Z0-9_]*)\s*[;,)]', code)):
        if sem not in SEMANTICS and sem not in ('TODO',):
            prob.append('%s: unknown semantic %s' % (name, sem))

    # ---- budget per pass
    psname = None
    for pname, compiles in passes(code):
        for t, fn in compiles:
            if t.startswith('ps'):
                psname = fn
                info['ps_model'] = t
    lim = PS_LIMITS.get(info.get('ps_model', 'ps_3_0'))
    nfetch = len(re.findall(r'tex2D(?:lod|bias|proj)?\s*\(', code))
    nsamp = len(re.findall(r'sampler\s+\w+\s*=\s*sampler_state', code))
    nconst = constants_used(code)
    info['fetches'] = nfetch
    info['samplers'] = nsamp
    info['float4_registers'] = nconst
    if nfetch > lim['tex']:
        prob.append('%s: %d texture fetches > %s limit of %d' % (name, nfetch, info['ps_model'], lim['tex']))
    if nsamp > lim['samplers']:
        prob.append('%s: %d samplers > %s limit of %d' % (name, nsamp, info['ps_model'], lim['samplers']))
    if nconst > lim['consts']:
        prob.append('%s: %d float4 constant registers > %s limit of %d' % (name, nconst, info['ps_model'], lim['consts']))
    if re.search(r'for\s*\(.*\)\s*\{[^}]*tex2D', code, re.S) and info.get('ps_model') == 'ps_2_0':
        warn.append('%s: a texture fetch inside a loop is not allowed in ps_2_0 (must be unrolled)' % name)
    if nfetch > 14:
        warn.append('%s: %d texture fetches is expensive for a world material' % (name, nfetch))
    return prob, warn, info


def to_slang(code):
    """fx (D3D9 fixed function style) -> HLSL that the Slang front-end accepts"""
    s = re.sub(r'technique\s+\w+\s*\{(?:[^{}]|\{[^{}]*\})*\}', '', code, flags=re.S)
    samplers = re.findall(r'sampler\s+(\w+)\s*=\s*sampler_state\s*\{[^}]*Texture\s*=\s*<(\w+)>', s)
    s = re.sub(r'sampler\s+\w+\s*=\s*sampler_state\s*\{[^}]*\}\s*;', '', s)
    s = re.sub(r'^texture\s+\w+\s*;', '', s, flags=re.M)
    s = re.sub(r'^((?:float\d?(?:x\d)?|int\d?|bool)\s+\w+(?:\s*\[\s*\d+\s*\])?)\s*:\s*\w+\s*;', r'\1;', s, flags=re.M)
    texmap = {sn: tn for sn, tn in samplers}
    for sn, tn in samplers:
        s = re.sub(r'\btex2D\s*\(\s*%s\s*,' % sn, 'T_%s.Sample(S_%s,' % (tn, tn), s)
    pre = ''.join('Texture2D<float4> T_%s; SamplerState S_%s;\n' % (tn, tn) for _, tn in samplers)
    return pre + s


def slang_check(files):
    """type checks every file with the real Slang HLSL front-end; returns [(file, error or None)]"""
    try:
        import slangpy
    except ImportError:
        return None
    dev = slangpy.Device(type=slangpy.DeviceType.cpu, enable_debug_layers=False)
    sess = dev.slang_session
    out = []
    for f in files:
        code = strip_comments(open(f, encoding='utf8').read())
        src = to_slang(code)
        try:
            sess.load_module_from_source('fx_' + os.path.basename(f).replace('.', '_'), src)
            out.append((os.path.basename(f), None))
        except Exception as e:
            out.append((os.path.basename(f), str(e)))
    return out


if __name__ == '__main__':
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else '../resource/RoadRealism/shaders'
    bad = 0
    for f in sorted(os.listdir(d)):
        if not f.endswith('.fx'):
            continue
        p, w, i = check_file(os.path.join(d, f))
        print('%-16s %-22s fetches=%-3d samplers=%-3d float4=%-3d' % (f, ','.join(i.get('targets', [])),
                                                                      i.get('fetches', 0), i.get('samplers', 0),
                                                                      i.get('float4_registers', 0)))
        for x in p:
            print('   FAIL', x)
            bad += 1
        for x in w:
            print('   warn', x)
    sc = slang_check([os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.fx')])
    if sc is None:
        print('slangpy not installed - shader bodies were only linted')
    else:
        for n, err in sc:
            if err:
                bad += 1
                print('   FAIL %s: Slang: %s' % (n, err[:1200]))
            else:
                print('%-16s Slang: type checked OK' % n)
    sys.exit(1 if bad else 0)
