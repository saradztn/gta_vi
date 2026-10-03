//----------------------------------------------------------------
// RoadRealism  -  post.fx
// Created by: Arena.ai Agent Mode (AI)
//
// Optional grade pass (enabled with /roadfx 3 or 4).  It exists so the wet road has something to
// sit in: a soft toe, a little contrast, a vignette and a rain-cooled tint.  Deliberately subtle -
// the point of the resource is the road material, not a colour filter.
// ps_2_0, one texture fetch.
//----------------------------------------------------------------

texture gSource;

sampler sSource = sampler_state { Texture = <gSource>; MinFilter = Linear; MagFilter = Linear; MipFilter = Point; AddressU = Clamp; AddressV = Clamp; };

float4 gGrade;      // x = exposure, y = contrast, z = saturation, w = vignette
float4 gTint;       // x = rain tint, y = night tint, z = grain, w = unused

struct VSInput
{
    float4 Position : POSITION0;
    float2 TexCoord : TEXCOORD0;
    float4 Diffuse  : COLOR0;
};

struct VSOutput
{
    float4 Position : POSITION0;
    float2 TexCoord : TEXCOORD0;
};

VSOutput PostVS(VSInput IN)
{
    VSOutput OUT = (VSOutput)0;
    OUT.Position = IN.Position;
    OUT.TexCoord = IN.TexCoord;
    return OUT;
}

float4 PostPS(VSOutput IN) : COLOR0
{
    float3 c = tex2D(sSource, IN.TexCoord).rgb;

    c *= gGrade.x;
    c = saturate((c - 0.5) * gGrade.y + 0.5);
    float l = dot(c, float3(0.299, 0.587, 0.114));
    c = lerp(l.xxx, c, gGrade.z);

    float2 d = IN.TexCoord - 0.5;
    float vig = saturate(1.0 - dot(d, d) * gGrade.w * 2.2);
    c *= vig;

    c = lerp(c, c * float3(0.94, 0.97, 1.05), gTint.x);
    c = lerp(c, c * float3(1.02, 0.99, 0.93), gTint.y);

    return float4(saturate(c), 1.0);
}

technique tec0
{
    pass P0
    {
        VertexShader = compile vs_2_0 PostVS();
        PixelShader = compile ps_2_0 PostPS();
    }
}

technique fallback
{
}
