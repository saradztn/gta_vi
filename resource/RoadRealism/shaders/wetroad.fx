//----------------------------------------------------------------
// RoadRealism  -  wetroad.fx
// Created by: Arena.ai Agent Mode (AI)
//
// The low / medium quality road shader: the same material model as road.fx, cut down to what fits
// the ps_2_0 budget - 7 texture fetches, no parallax, one local light, one reflection tap.
// It is also the shader that runs when a driver refuses road.fx, so every preset keeps the full
// wet / puddle / marking behaviour; only the detail density and the reflection quality change.
//
// Constant registers are packed exactly like in road.fx (gRoadA..gRoadF), so the Lua side uses one
// interface for both.  Total: 22 float4 registers - inside the ps_2_0 limit of 32.
//----------------------------------------------------------------

float4 gRoadA, gRoadB, gRoadC, gRoadD, gRoadE, gRoadF;
#define gWet              gRoadA.x
#define gPuddleLevel      gRoadA.z
#define gNight            gRoadA.w
#define gExposure         gRoadB.x
#define gAlbedoLift       gRoadB.y
#define gWorldScale       gRoadB.z
#define gMeshUVScale      gRoadC.x
#define gUseMeshUV        gRoadC.y
#define gNormalScale      gRoadC.z
#define gMarkingRough     gRoadD.x
#define gMarkingRetro     gRoadD.y
#define gRetroBoost       gRoadD.z
#define gHasMarking       gRoadD.w
#define gOriginalMix      gRoadE.x
#define gReflectStrength  gRoadE.y
#define gReflectStretch   gRoadE.w
#define gReflectAnglePow  gRoadF.x
#define gSunSpec          gRoadF.y

texture gAlbedo;
texture gMask;
texture gDetailNormal;
texture gPuddle;
texture gMarking;
texture gScreen;
texture Tex0;

sampler sAlbedo       = sampler_state { Texture = <gAlbedo>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMask         = sampler_state { Texture = <gMask>;         MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sDetailNormal = sampler_state { Texture = <gDetailNormal>; MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sPuddle       = sampler_state { Texture = <gPuddle>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sMarking      = sampler_state { Texture = <gMarking>;      MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };
sampler sScreen       = sampler_state { Texture = <gScreen>;       MinFilter = Linear; MagFilter = Linear; MipFilter = Point;  AddressU = Clamp; AddressV = Clamp; };
sampler sOriginal     = sampler_state { Texture = <Tex0>;          MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };

float4x4 gWorldViewProjection : WORLDVIEWPROJECTION;
float4x4 gViewProjection      : VIEWPROJECTION;
float3   gCameraPosition      : CAMERAPOSITION;

float4 gSun;
float4 gSunColor;
float4 gLightColor;
float4 gLights0;
float4 gScreenSize;
float4 gFog;
float4 gFogColor;

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

struct PSInput
{
    float2 TexCoord  : TEXCOORD0;
    float3 WorldPos  : TEXCOORD1;
    float3 Normal    : TEXCOORD2;
    float4 Diffuse   : COLOR0;
};

float sstep(float a, float b, float x)
{
    float t = saturate((x - a) / max(b - a, 1e-5));
    return t * t * (3 - 2 * t);
}

void TangentFrame(float3 n, out float3 T, out float3 B)
{
    float3 up = (abs(n.z) < 0.9) ? float3(0, 0, 1) : float3(1, 0, 0);
    T = normalize(cross(up, n));
    B = cross(n, T);
}

float4 RoadPS(PSInput IN) : COLOR0
{
    float3 nGeo = normalize(IN.Normal);
    float3 V = normalize(gCameraPosition - IN.WorldPos);
    float3 T, B;
    TangentFrame(nGeo, T, B);

    float2 uvWorld = float2(dot(IN.WorldPos, T), dot(IN.WorldPos, B)) / max(gWorldScale, 0.05);
    float2 uvMesh = IN.TexCoord * gMeshUVScale;
    float2 uvBase = (gUseMeshUV > 0.5) ? uvMesh : uvWorld;

    float3 albedo = tex2D(sAlbedo, uvBase).rgb;
    float4 mask = tex2D(sMask, uvBase);
    float3 pud = tex2D(sPuddle, uvBase * 0.55).rgb;
    float4 mk = tex2D(sMarking, uvMesh);

    float4 nm = tex2D(sDetailNormal, uvBase * 8.0);
    float2 nxy = (float2(nm.a, nm.g) * 2 - 1) * gNormalScale;
    float nz = sqrt(saturate(1 - dot(nxy, nxy)));
    float3 N = normalize(T * nxy.x + B * nxy.y + nGeo * nz);

    // contamination and damage
    float oil = saturate(mask.a * 1.4 - 0.25);
    float dust = saturate(mask.a - oil * 0.6);
    albedo *= (1.0 - 0.42 * mask.b) * (1.0 - 0.40 * oil) * (1.0 - 0.16 * dust);
    albedo += float3(0.055, 0.045, 0.028) * dust;
    float rough = saturate(mask.r * (1.0 - 0.55 * oil) + 0.22 * dust + 0.12 * mask.b);
    float f0 = 0.02 + 0.03 * oil;

    float cover = saturate(mk.a * gHasMarking);
    albedo = lerp(albedo, mk.rgb * 1.05, cover);
    rough = lerp(rough, gMarkingRough, cover);
    albedo = lerp(albedo, tex2D(sOriginal, IN.TexCoord).rgb, gOriginalMix);
    albedo = saturate(pow(albedo, 2.2)) * gAlbedoLift;

    // wetness + puddles: a water film darkens the diffuse and collapses the roughness
    float pudMask = sstep(1.0 - gPuddleLevel * 0.95, 1.0 - gPuddleLevel * 0.95 + 0.25, pud.r);
    float film = saturate(max(gWet, pudMask)) * (0.55 + 0.45 * pudMask);
    albedo *= lerp(1.0, 0.62, film);
    rough = lerp(rough, lerp(0.09, 0.035, pudMask), film);
    float ao = saturate(mask.g * lerp(1.0, 0.85, film));

    float3 col = albedo * IN.Diffuse.rgb * gExposure * ao;

    // one Blinn-Phong lobe shaped by the roughness
    float3 H = normalize(gSun.xyz + V);
    float a = max(rough * rough, 0.012);
    float p = max(2.0 / (a * a) - 2.0, 2.0);
    float vh = saturate(dot(V, H));
    float fres = f0 + (1 - f0) * pow(1 - vh, 5);
    col += gSunColor.rgb * gSun.w * gSunSpec * pow(saturate(dot(N, H)), p) * ((p + 8.0) / 25.13) * fres;

    // one local light (the nearest vehicle headlights)
    float3 dv = gLights0.xyz - IN.WorldPos;
    float d2 = max(dot(dv, dv), 0.35);
    float at = gLights0.w / (1.0 + d2 * 0.09);
    float3 L = dv * rsqrt(d2);
    col += albedo * gLightColor.rgb * at * saturate(dot(N, L)) * ao;

    // retroreflection of the painted lines
    col += gLightColor.rgb * pow(saturate(dot(N, V)), 6.0) * gMarkingRetro * gRetroBoost * cover * (gNight + at) * 0.65;

    // reflection: one tap, the blur is done once per frame by reflection.fx
    float reflAmt = gReflectStrength * film * pow(1.0 - saturate(dot(N, V)), gReflectAnglePow) * 1.6;
    float3 R = 2.0 * dot(N, V) * N - V;
    float4 cp = mul(float4(IN.WorldPos + R * 1.4, 1), gViewProjection);
    float2 suv = float2(cp.x / max(cp.w, 0.02), -cp.y / max(cp.w, 0.02)) * 0.5 + 0.5;
    suv.y = saturate(0.5 + (suv.y - 0.5) * gReflectStretch);
    float3 refl = pow(saturate(tex2D(sScreen, saturate(suv)).rgb), 1.35) * float3(0.92, 0.95, 1.0);
    col += refl * reflAmt * (0.35 + 0.65 * gNight);

    float dist = length(gCameraPosition - IN.WorldPos);
    col = lerp(col, gFogColor.rgb * gExposure, sstep(gFog.x, gFog.y, dist));
    return float4(saturate(col), IN.Diffuse.a);
}

technique tec0
{
    pass P0
    {
        VertexShader = compile vs_2_0 RoadVS();
        PixelShader = compile ps_2_0 RoadPS();
    }
}

technique fallback
{
}
