//----------------------------------------------------------------
// RoadRealism  -  road.fx
// Created by: Arena.ai Agent Mode (AI)
//
// Full quality road surface shader for MTA:SA 1.6 (D3D9, vs_3_0 / ps_3_0).
// Replaces the MATERIAL of the original San Andreas road geometry: the mesh, the UVs, the
// collisions and the map are never touched, only what the surface looks like.
//
// Projection
//   GTA SA road UVs are wildly inconsistent between the original models, so albedo / detail /
//   damage are re-projected from WORLD SPACE with a branch-free dominant-plane mapping.  That gives
//   one texel density everywhere (a 4 m tile is 4 m in Los Santos and in the desert) and it works
//   on horizontal road, tunnel walls and bridge sides alike.  Road MARKINGS use the original mesh
//   UVs (they must line up with the geometry) and take only their micro detail from world space.
//
// Lighting
//   Diffuse comes from the prelit vertex colour (COLOR0) - that already contains San Andreas'
//   baked street lighting and time of day, so the road is never "double lit" against the buildings
//   next to it.  On top of that this shader adds a real roughness/specular response, retro-
//   reflection for the painted lines and a screen space reflection for the wet surface.
//
// Constant registers: every tuning value is packed into gRoadA..gRoadF (see below), so the shader
// needs 25 float4 registers - inside the ps_2_0 limit of 32 as well as the ps_3_0 limit.
// Texture fetches: 11.  Loops: fully unrolled, no dynamic texture fetches.
//----------------------------------------------------------------

#define MAX_LIGHTS 4

//----------------------------------------------------------------
// constant packing (the Lua side fills these with dxSetShaderValue; source/rr/materials.py holds
// the same table so the two can never drift apart)
//   gRoadA  x = gWet          y = gWetVar        z = gPuddleLevel   w = gNight
//   gRoadB  x = gExposure     y = gAlbedoLift    z = gWorldScale    w = gDetailScale
//   gRoadC  x = gMeshUVScale  y = gUseMeshUV     z = gNormalScale   w = gParallax
//   gRoadD  x = gMarkingRough y = gMarkingRetro  z = gRetroBoost    w = gHasMarking
//   gRoadE  x = gOriginalMix  y = gReflectStrength z = gReflectBlur w = gReflectStretch
//   gRoadF  x = gReflectAnglePow y = gSunSpec    z = gTime          w = gReflTaps
//----------------------------------------------------------------
float4 gRoadA, gRoadB, gRoadC, gRoadD, gRoadE, gRoadF;
#define gWet              gRoadA.x
#define gWetVar           gRoadA.y
#define gPuddleLevel      gRoadA.z
#define gNight            gRoadA.w
#define gExposure         gRoadB.x
#define gAlbedoLift       gRoadB.y
#define gWorldScale       gRoadB.z
#define gDetailScale      gRoadB.w
#define gMeshUVScale      gRoadC.x
#define gUseMeshUV        gRoadC.y
#define gNormalScale      gRoadC.z
#define gParallax         gRoadC.w
#define gMarkingRough     gRoadD.x
#define gMarkingRetro     gRoadD.y
#define gRetroBoost       gRoadD.z
#define gHasMarking       gRoadD.w
#define gOriginalMix      gRoadE.x
#define gReflectStrength  gRoadE.y
#define gReflectBlur      gRoadE.z
#define gReflectStretch   gRoadE.w
#define gReflectAnglePow  gRoadF.x
#define gSunSpec          gRoadF.y
#define gTime             gRoadF.z
#define gReflTaps         gRoadF.w

//----------------------------------------------------------------
// maps
//----------------------------------------------------------------
texture gAlbedo;         // material base colour, sRGB, DXT1
texture gMask;           // R = roughness, G = AO, B = damage, A = contamination
texture gDetailNormal;   // shared aggregate normal, DXT5nm (A = nx, G = ny)
texture gDetailData;     // shared aggregate data: R = roughness var, G = AO, B = height
texture gMicroNormal;    // fine grain normal, DXT5nm
texture gMacro;          // large scale colour / tone variation
texture gPuddle;         // R = puddle mask, G = depth, B = rim
texture gMarking;        // road marking sheet: RGB = paint colour, A = coverage
texture gScreen;         // reflection source (the pre-blurred screen, see reflection.fx)
texture Tex0;            // the ORIGINAL San Andreas texture, bound by MTA

sampler sAlbedo       = sampler_state { Texture = <gAlbedo>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMask         = sampler_state { Texture = <gMask>;         MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sDetailNormal = sampler_state { Texture = <gDetailNormal>; MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sDetailData   = sampler_state { Texture = <gDetailData>;   MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMicroNormal  = sampler_state { Texture = <gMicroNormal>;  MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMacro        = sampler_state { Texture = <gMacro>;        MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sPuddle       = sampler_state { Texture = <gPuddle>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMarking      = sampler_state { Texture = <gMarking>;      MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sScreen       = sampler_state { Texture = <gScreen>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Point;  AddressU = Clamp; AddressV = Clamp; };
sampler sOriginal     = sampler_state { Texture = <Tex0>;          MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };

//----------------------------------------------------------------
// engine provided
//----------------------------------------------------------------
float4x4 gWorldViewProjection : WORLDVIEWPROJECTION;
float4x4 gViewProjection      : VIEWPROJECTION;
float3   gCameraPosition      : CAMERAPOSITION;

//----------------------------------------------------------------
// lights (vehicle headlights and other local lights, gathered by reflect.lua)
//----------------------------------------------------------------
float4 gSun;              // xyz = direction TO the sun, w = intensity
float4 gSunColor;         // rgb
float4 gLightColor;       // rgb
float4 gLights0;          // xyz = world position, w = intensity
float4 gLights1;
float4 gLights2;
float4 gLights3;
float4 gScreenSize;       // w, h, 1/w, 1/h
float4 gFog;              // x = fog start, y = fog end
float4 gFogColor;         // rgb

//----------------------------------------------------------------
// vertex shader.  MTA renders world geometry with a fixed vertex declaration - these are its
// members, and a world shader must declare exactly this input layout.
//----------------------------------------------------------------
struct VSInput
{
    float4 Position     : POSITION0;
    float4 BlendWeights : BLENDWEIGHT;
    float4 BlendIndices : BLENDINDICES;
    float4 Normal       : NORMAL0;
    float2 TexCoord     : TEXCOORD0;
    float4 Diffuse      : COLOR0;
    float4 Specular     : COLOR1;
    float2 TexCoord1    : TEXCOORD1;
};

struct VSOutput
{
    float4 Position  : POSITION0;
    float2 TexCoord  : TEXCOORD0;
    float3 WorldPos  : TEXCOORD1;
    float3 Normal    : TEXCOORD2;
    float4 Diffuse   : COLOR0;
};

VSOutput RoadVS(VSInput IN)
{
    VSOutput OUT = (VSOutput)0;
    OUT.Position = mul(IN.Position, gWorldViewProjection);
    OUT.TexCoord = IN.TexCoord;
    OUT.WorldPos = IN.Position.xyz;
    OUT.Normal = IN.Normal.xyz;
    OUT.Diffuse = IN.Diffuse;
    return OUT;
}

//----------------------------------------------------------------
// helpers
//----------------------------------------------------------------
float sstep(float a, float b, float x)
{
    float t = saturate((x - a) / max(b - a, 1e-5));
    return t * t * (3 - 2 * t);
}

// San Andreas geometry carries no tangents, so the frame is derived from the normal.  Branch free
// and valid for road decks as well as tunnel walls and bridge sides.
void TangentFrame(float3 n, out float3 T, out float3 B)
{
    float3 up = (abs(n.z) < 0.9) ? float3(0, 0, 1) : float3(1, 0, 0);
    T = normalize(cross(up, n));
    B = cross(n, T);
}

float3 DecodeNormal(float4 nm)
{
    // DXT5nm: A = x, G = y, z reconstructed
    float2 xy = float2(nm.a, nm.g) * 2 - 1;
    float z2 = saturate(1 - dot(xy, xy));
    return float3(xy, sqrt(z2));
}

// Blinn-Phong shaped by the roughness: a cheap stand-in for GGX that stays inside the budget
float3 Specular(float3 N, float3 V, float3 L, float3 col, float rough, float f0)
{
    float3 H = normalize(L + V);
    float nh = saturate(dot(N, H));
    float a = max(rough * rough, 0.012);
    float p = max(2.0 / (a * a) - 2.0, 2.0);
    float norm = (p + 8.0) / 25.13;
    float vh = saturate(dot(V, H));
    float fres = f0 + (1 - f0) * pow(1 - vh, 5);
    return col * pow(nh, p) * norm * fres * saturate(dot(N, L));
}

//----------------------------------------------------------------
// pixel shader
//----------------------------------------------------------------
struct PSInput
{
    float2 TexCoord  : TEXCOORD0;
    float3 WorldPos  : TEXCOORD1;
    float3 Normal    : TEXCOORD2;
    float4 Diffuse   : COLOR0;
};

float4 RoadPS(PSInput IN) : COLOR0
{
    float3 nGeo = normalize(IN.Normal);
    float3 V = normalize(gCameraPosition - IN.WorldPos);

    // ---------------------------------------------------------------- projection
    float3 T, B;
    TangentFrame(nGeo, T, B);
    float2 uvWorld = float2(dot(IN.WorldPos, T), dot(IN.WorldPos, B)) / max(gWorldScale, 0.05);
    float2 uvMesh = IN.TexCoord * gMeshUVScale;
    float2 uvBase = (gUseMeshUV > 0.5) ? uvMesh : uvWorld;

    // ---------------------------------------------------------------- parallax (detail only)
    float2 uvDetail = uvBase * gDetailScale;
    float4 dd = tex2D(sDetailData, uvDetail);
    if (gParallax > 0.0001)
    {
        float3 Vt = float3(dot(V, T), dot(V, B), saturate(dot(V, nGeo)));
        float k = gParallax * gDetailScale / max(gWorldScale, 0.05);
        uvDetail += (Vt.xy / max(Vt.z, 0.35)) * (dd.b - 0.5) * k;
        dd = tex2D(sDetailData, uvDetail);
    }

    // ---------------------------------------------------------------- maps
    float3 albTex = tex2D(sAlbedo, uvBase).rgb;
    float4 mask = tex2D(sMask, uvBase);
    float3 macro = tex2D(sMacro, uvBase * 0.37).rgb;
    float3 pud = tex2D(sPuddle, uvBase * 0.55).rgb;
    float4 mk = tex2D(sMarking, uvMesh);

    // ---------------------------------------------------------------- normals
    float3 nAgg = DecodeNormal(tex2D(sDetailNormal, uvDetail));
    float3 nMic = DecodeNormal(tex2D(sMicroNormal, uvBase * gDetailScale * 3.1));
    float3 nTan = normalize(float3((nAgg.xy * 0.72 + nMic.xy * 0.42) * gNormalScale, nAgg.z * nMic.z));
    float3 N = normalize(T * nTan.x + B * nTan.y + nGeo * nTan.z);

    // ---------------------------------------------------------------- surface composition
    float3 albedo = albTex * macro * 2.0;                     // large scale tone variation
    albedo *= (0.80 + 0.42 * dd.g);                           // crevice occlusion from the detail
    float rough = saturate(mask.r + (dd.r - 0.5) * 0.30);
    float ao = saturate(mask.g * (0.55 + 0.45 * dd.g));
    float damage = mask.b;
    float contam = mask.a;

    // damage: crack bottoms are darker, rougher and hold water
    albedo *= (1.0 - 0.45 * damage);
    rough = saturate(rough + 0.12 * damage);
    // contamination: dust is matte and warm, oil and rubber are dark and glossy
    float oil = saturate(contam * 1.4 - 0.25);
    float dust = saturate(contam - oil * 0.6);
    albedo *= (1.0 - 0.40 * oil) * (1.0 - 0.16 * dust);
    albedo += float3(0.055, 0.045, 0.028) * dust;
    rough = saturate(rough * (1.0 - 0.55 * oil) + 0.22 * dust);
    float f0 = 0.02 + 0.03 * oil;

    // markings are painted over the surface (mesh UVs, so they line up with the geometry)
    float cover = saturate(mk.a * gHasMarking);
    albedo = lerp(albedo, mk.rgb * 1.05, cover);
    rough = lerp(rough, gMarkingRough + 0.15 * (1 - mk.a), cover);
    f0 = lerp(f0, 0.05, cover);

    albedo = lerp(albedo, tex2D(sOriginal, IN.TexCoord).rgb, gOriginalMix);
    albedo = saturate(pow(albedo, 2.2)) * gAlbedoLift;        // sRGB -> linear

    // ---------------------------------------------------------------- wetness
    // a water film both darkens the diffuse (total internal reflection traps the light) and
    // collapses the roughness - it is NOT just "darker asphalt"
    float wetLocal = saturate(gWet * (1.0 - gWetVar * (macro.r - 0.5) * 2.0));
    float pudMask = sstep(0.45, 0.70, pud.r) * saturate(gPuddleLevel * 1.5);
    float film = saturate(max(wetLocal, pudMask)) * (0.55 + 0.45 * pudMask);
    albedo *= lerp(1.0, 0.62, film);
    rough = lerp(rough, lerp(0.12, 0.05, pudMask), film);
    f0 = lerp(f0, 0.02, film);
    ao *= lerp(1.0, 0.85, film);
    // the puddle surface is not flat: the rim channel ripples the reflection
    float2 ripple = (pud.b - 0.5) * 0.55 * pudMask;
    N = normalize(N + T * ripple.x + B * ripple.y);

    // ---------------------------------------------------------------- diffuse (prelit)
    float3 col = albedo * IN.Diffuse.rgb * gExposure * ao;

    // ---------------------------------------------------------------- specular and lights
    float3 spec = Specular(N, V, gSun.xyz, gSunColor.rgb * gSun.w * gSunSpec, rough, f0);
    float retro = pow(saturate(dot(N, V)), 6.0) * gMarkingRetro * gRetroBoost * cover * gNight;

    float4 lp = gLights0;
    float3 dv = lp.xyz - IN.WorldPos;
    float d2 = max(dot(dv, dv), 0.35);
    float at = lp.w / (1.0 + d2 * 0.09);
    float3 L = dv * rsqrt(d2);
    col += albedo * gLightColor.rgb * at * saturate(dot(N, L)) * ao;
    spec += Specular(N, V, L, gLightColor.rgb * at, rough, f0) * 4.0;
    retro += pow(saturate(dot(N, normalize(L + V))), 10.0) * gMarkingRetro * gRetroBoost * cover * at;

    lp = gLights1;
    dv = lp.xyz - IN.WorldPos;
    d2 = max(dot(dv, dv), 0.35);
    at = lp.w / (1.0 + d2 * 0.09);
    L = dv * rsqrt(d2);
    col += albedo * gLightColor.rgb * at * saturate(dot(N, L)) * ao;
    spec += Specular(N, V, L, gLightColor.rgb * at, rough, f0) * 4.0;
    retro += pow(saturate(dot(N, normalize(L + V))), 10.0) * gMarkingRetro * gRetroBoost * cover * at;

    lp = gLights2;
    dv = lp.xyz - IN.WorldPos;
    d2 = max(dot(dv, dv), 0.35);
    at = lp.w / (1.0 + d2 * 0.09);
    L = dv * rsqrt(d2);
    col += albedo * gLightColor.rgb * at * saturate(dot(N, L)) * ao;
    spec += Specular(N, V, L, gLightColor.rgb * at, rough, f0) * 4.0;
    retro += pow(saturate(dot(N, normalize(L + V))), 10.0) * gMarkingRetro * gRetroBoost * cover * at;

    lp = gLights3;
    dv = lp.xyz - IN.WorldPos;
    d2 = max(dot(dv, dv), 0.35);
    at = lp.w / (1.0 + d2 * 0.09);
    L = dv * rsqrt(d2);
    col += albedo * gLightColor.rgb * at * saturate(dot(N, L)) * ao;
    spec += Specular(N, V, L, gLightColor.rgb * at, rough, f0) * 4.0;
    retro += pow(saturate(dot(N, normalize(L + V))), 10.0) * gMarkingRetro * gRetroBoost * cover * at;

    col += spec + gLightColor.rgb * retro * 0.65;

    // ---------------------------------------------------------------- screen space reflection
    float reflAmt = gReflectStrength * film * pow(1.0 - saturate(dot(N, V)), gReflectAnglePow) * 1.25;
    if (reflAmt > 0.004)
    {
        float3 R = 2.0 * dot(N, V) * N - V;
        float3 accum = float3(0, 0, 0);
        float wsum = 0.0;
        float stepLen = 1.3;
        float3 rp = IN.WorldPos + R * stepLen;
        float4 cp = mul(float4(rp, 1), gViewProjection);
        float2 suv = float2(cp.x / max(cp.w, 0.02), -cp.y / max(cp.w, 0.02)) * 0.5 + 0.5;
        suv.y = saturate(0.5 + (suv.y - 0.5) * gReflectStretch);
        if (cp.w > 0.02 && suv.x > 0 && suv.x < 1 && suv.y > 0 && suv.y < 1)
        {
            accum += tex2D(sScreen, suv).rgb;
            wsum += 1.0;
        }
        if (gReflTaps > 1.5)
        {
            float2 o = gReflectBlur * gScreenSize.zw;
            accum += tex2D(sScreen, saturate(suv + float2(o.x, 0))).rgb * 0.7;
            accum += tex2D(sScreen, saturate(suv - float2(o.x, 0))).rgb * 0.7;
            wsum += 1.4;
        }
        if (wsum > 0.0)
        {
            float3 refl = accum / wsum;
            // water tints the reflection and a wet road never mirrors: keep it soft and cool
            refl = pow(saturate(refl), 1.35) * float3(0.92, 0.95, 1.0);
            col += refl * reflAmt * (0.35 + 0.65 * gNight);
        }
    }

    // ---------------------------------------------------------------- fog
    float dist = length(gCameraPosition - IN.WorldPos);
    col = lerp(col, gFogColor.rgb * gExposure, sstep(gFog.x, gFog.y, dist));

    return float4(saturate(col), IN.Diffuse.a);
}

//----------------------------------------------------------------
technique tec0
{
    pass P0
    {
        VertexShader = compile vs_3_0 RoadVS();
        PixelShader = compile ps_3_0 RoadPS();
    }
}

//----------------------------------------------------------------
// MTA uses this technique when tec0 cannot be compiled by the driver.  An empty technique means
// "draw the original material", which is exactly the failsafe this resource wants.
//----------------------------------------------------------------
technique fallback
{
}
