// Renders the real game code (source/main.c) headlessly and dumps both screens as PPM files.
//   python3 tools/preview/run_preview.py     (does everything)
#define main game_main
#include "../../source/main.c"
#undef main

static const char *outdir;
static void dump(const char *name) {
    char path[256];
    C3D_RenderTarget *t[2] = {&stubTop, &stubBot};
    const char *sfx_[2] = {"top", "bot"};
    for (int i = 0; i < 2; i++) {
        snprintf(path, sizeof path, "%s/%s_%s.ppm", outdir, name, sfx_[i]);
        FILE *f = fopen(path, "wb");
        fprintf(f, "P6\n%d %d\n255\n", t[i]->w, t[i]->h);
        for (int p = 0; p < t[i]->w * t[i]->h; p++) fwrite(t[i]->px + p * 4, 1, 3, f);
        fclose(f);
    }
}

typedef struct { unsigned f; const char *name; } Shot;
static const Shot shots[] = {
    {2, "01_title"}, {20, "02_egg"}, {40, "03_frog_needs"}, {50, "04_cursor"}, {60, "05_feed"},
    {75, "06_info"}, {90, "07_game"}, {140, "08_game_later"}, {150, "09_night"}, {160, "10_tadpole_msg"},
    {170, "11_elder_sick"},
};

static void key(u32 k) { stub_kdown |= k; stub_kheld |= k; }
static void input(unsigned f) {
    switch (f) {
    case 3: key(KEY_A); break;                                   // leave title
    case 25:                                                     // grown-up frog with problems
        g_new(&G, (int64_t)time(NULL)); g_step(&G, 50, 1); g_skip(&G, 30 * 3600);
        G.fainted = 0; G.sick = 0; G.food = 18; G.joy = 40; G.clean = 55; G.energy = 70; G.health = 85; G.poops = 2; msgT = 0;
        break;
    case 45: key(KEY_DRIGHT); break;
    case 55: cursor = 0; key(KEY_A); break;                      // open feed menu
    case 65: key(KEY_B); break;
    case 70: cursor = 5; key(KEY_A); break;                      // info
    case 80: key(KEY_B); break;
    case 85: cursor = 1; key(KEY_A); break;                      // play
    case 100: case 110: case 120: key(KEY_TOUCH); stub_touch.px = (u16)flies[0].x + 16; stub_touch.py = (u16)flies[0].y + 16; break;
    case 145: scr = SCR_MAIN; G.sleeping = 1; G.energy = 30; break;
    case 155: G.sleeping = 0; g_new(&G, (int64_t)time(NULL)); g_step(&G, 50, 1); G.food = 90; msgT = 0; set_msg("PLOP! GERALD POOPED.\nTAP CLEAN SOON."); break;
    case 165: g_new(&G, (int64_t)time(NULL)); g_step(&G, 50, 1); g_skip(&G, 6 * 24 * 3600); G.sick = 1; msgT = 0; break;
    }
}
static void frame_end(unsigned f) {
    for (unsigned i = 0; i < sizeof shots / sizeof *shots; i++)
        if (shots[i].f == f) dump(shots[i].name);
}
int main(int argc, char **argv) {
    outdir = argc > 1 ? argv[1] : ".";
    stub_input_hook = input;
    stub_frame_hook = frame_end;
    stub_max_frames = 175;
    return game_main(0, NULL);
}
