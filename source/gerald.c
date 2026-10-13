#include "gerald.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Tuning. Everything is "per hour of real time" unless noted.
// ---------------------------------------------------------------------------
#define HOUR 3600.0

#define EGG_HATCH_SECONDS   45.0
#define AGE_FROGLET         (4.0 * HOUR)
#define AGE_FROG            (24.0 * HOUR)
#define AGE_ELDER           (5.0 * 24.0 * HOUR)

#define FOOD_DECAY_AWAKE    18.0f
#define FOOD_DECAY_ASLEEP    5.0f
#define JOY_DECAY_AWAKE     12.0f
#define JOY_DECAY_ASLEEP     3.0f
#define CLEAN_DECAY_BASE     3.0f
#define CLEAN_DECAY_PER_POOP 12.0f
#define ENERGY_DECAY_AWAKE   9.0f
#define ENERGY_GAIN_ASLEEP  45.0f

#define HEALTH_REGEN         8.0f
#define HEALTH_LOSS_CRIT    12.0f   // per critical stat
#define HEALTH_LOSS_SICK    15.0f

#define OFFLINE_CAP_SECONDS (10.0 * HOUR)  // longest stretch that is simulated while closed
#define OFFLINE_SCALE       0.5            // ...and at half speed, so a night away is not a disaster

enum { F_HUNGRY = 1, F_SLEEPY = 2, F_DIRTY = 4, F_SAD = 8 };

static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static uint32_t rnd(Gerald *g) {
    uint32_t x = g->rng ? g->rng : 0x9E3779B9u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g->rng = x;
    return x;
}
static float rnd01(Gerald *g) { return (rnd(g) & 0xFFFFFF) / (float)0x1000000; }

static uint32_t checksum_of(const Gerald *g) {
    const uint8_t *p = (const uint8_t *)g;
    size_t n = offsetof(Gerald, checksum);
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
    return h;
}

// ---------------------------------------------------------------------------
void g_new(Gerald *g, int64_t now) {
    memset(g, 0, sizeof(*g));
    g->magic = G_MAGIC;
    g->version = G_VERSION;
    g->stage = G_EGG;
    g->food = 80; g->joy = 80; g->clean = 100; g->energy = 100; g->health = 100;
    g->poop_timer = -1;
    g->last_time = now;
    g->rng = (uint32_t)(now ^ 0xA5F00D17u);
}

bool g_save(const Gerald *g, const char *path) {
    Gerald copy = *g;
    copy.checksum = checksum_of(&copy);
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    bool ok = fwrite(&copy, sizeof(copy), 1, f) == 1;
    fclose(f);
    return ok;
}

bool g_load(Gerald *g, const char *path) {
    Gerald tmp;
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    bool ok = fread(&tmp, sizeof(tmp), 1, f) == 1;
    fclose(f);
    if (!ok || tmp.magic != G_MAGIC || tmp.version != G_VERSION || tmp.checksum != checksum_of(&tmp)) return false;
    if (tmp.stage > G_ELDER) return false;
    *g = tmp;
    return true;
}

// ---------------------------------------------------------------------------
static int stage_for_age(double age) {
    if (age >= AGE_ELDER) return G_ELDER;
    if (age >= AGE_FROG) return G_FROG;
    if (age >= AGE_FROGLET) return G_FROGLET;
    return G_TADPOLE;
}

static uint32_t check_growth(Gerald *g) {
    if (g->stage == G_EGG) return 0;
    int s = stage_for_age(g->age);
    if (s > g->stage) { g->stage = (uint8_t)s; return EV_EVOLVED; }
    return 0;
}

static uint32_t edge(Gerald *g, bool cond, uint8_t flag, uint32_t ev) {
    if (cond && !(g->flags & flag)) { g->flags |= flag; return ev; }
    if (!cond) g->flags &= (uint8_t)~flag;
    return 0;
}

uint32_t g_step(Gerald *g, double dt, double scale) {
    uint32_t ev = 0;
    if (dt <= 0) return 0;

    if (g->stage == G_EGG) {
        g->egg_time += dt;
        if (g->egg_time >= EGG_HATCH_SECONDS) {
            g->stage = G_TADPOLE;
            g->age = 0;
            ev |= EV_HATCHED;
        }
        return ev;
    }

    g->age += dt;
    ev |= check_growth(g);

    if (g->fainted) return ev;          // frozen until medicine

    float r = (float)(dt * scale / HOUR);   // hours of "pet time"
    bool asleep = g->sleeping;

    g->food  -= (asleep ? FOOD_DECAY_ASLEEP : FOOD_DECAY_AWAKE) * r;
    g->joy   -= (asleep ? JOY_DECAY_ASLEEP : JOY_DECAY_AWAKE) * (g->sick ? 2.0f : 1.0f) * r;
    g->clean -= (CLEAN_DECAY_BASE + CLEAN_DECAY_PER_POOP * g->poops) * r;
    if (asleep) {
        g->energy += ENERGY_GAIN_ASLEEP * r;
        if (g->energy >= 100.0f) { g->energy = 100.0f; g->sleeping = 0; ev |= EV_WOKE; }
    } else {
        g->energy -= ENERGY_DECAY_AWAKE * r;
    }
    g->snack_load = clampf(g->snack_load - 6.0f * r, 0, 10);   // a snack "wears off" in ~10 min

    // pooping
    if (g->poop_timer >= 0) {
        g->poop_timer -= (float)(dt * scale);
        if (g->poop_timer < 0) {
            if (g->poops < G_MAX_POOPS) { g->poops++; ev |= EV_POOPED; }
            g->poop_timer = -1;
        }
    }

    g->food = clampf(g->food, 0, 100);
    g->joy = clampf(g->joy, 0, 100);
    g->clean = clampf(g->clean, 0, 100);
    g->energy = clampf(g->energy, 0, 100);

    // getting ill: baseline + filth + neglect
    if (!g->sick) {
        float lambda = 0.01f;                       // per hour
        if (g->clean < 25) lambda += 0.5f;
        if (g->poops >= 3) lambda += 0.5f;
        if (g->food < 10) lambda += 0.2f;
        if (rnd01(g) < lambda * r) { g->sick = 1; ev |= EV_SICK; }
    }

    // health
    int crit = (g->food < 15) + (g->joy < 15) + (g->clean < 15) + (g->energy < 10 && !asleep);
    float dh = 0;
    if (crit) dh -= HEALTH_LOSS_CRIT * crit;
    if (g->sick) dh -= HEALTH_LOSS_SICK;
    if (!crit && !g->sick && g->food > 30 && g->joy > 30 && g->clean > 30 && g->energy > 20) dh += HEALTH_REGEN;
    g->health = clampf(g->health + dh * r, 0, 100);
    if (g->health <= 0.0f) {
        g->fainted = 1;
        g->sleeping = 0;
        ev |= EV_FAINTED;
    }

    // notifications (edge triggered so we don't nag)
    ev |= edge(g, g->food < 25, F_HUNGRY, EV_HUNGRY);
    ev |= edge(g, !g->sleeping && g->energy < 20, F_SLEEPY, EV_SLEEPY);
    ev |= edge(g, g->poops >= 2 || g->clean < 30, F_DIRTY, EV_DIRTY);
    ev |= edge(g, g->joy < 25, F_SAD, EV_SAD);
    return ev;
}

static uint32_t simulate(Gerald *g, double seconds, double scale) {
    uint32_t ev = 0;
    const double chunk = 20.0;
    while (seconds > 0) {
        double d = seconds < chunk ? seconds : chunk;
        ev |= g_step(g, d, scale);
        seconds -= d;
    }
    return ev;
}

uint32_t g_catchup(Gerald *g, int64_t now) {
    double elapsed = (double)(now - g->last_time);
    g->last_time = now;
    if (elapsed <= 1.0) return 0;               // also covers the clock going backwards
    double sim = elapsed < OFFLINE_CAP_SECONDS ? elapsed : OFFLINE_CAP_SECONDS;
    uint32_t ev = simulate(g, sim, OFFLINE_SCALE);
    if (elapsed > sim && g->stage != G_EGG) {   // any extra time only makes him older
        g->age += elapsed - sim;
        ev |= check_growth(g);
    }
    return ev;
}

uint32_t g_skip(Gerald *g, double seconds) { return simulate(g, seconds, 1.0); }

// ---------------------------------------------------------------------------
Mood g_mood(const Gerald *g) {
    if (g->fainted) return M_FAINT;
    if (g->sleeping) return M_SLEEP;
    if (g->sick) return M_SICK;
    float lo = g->food < g->joy ? g->food : g->joy;
    if (g->clean < lo) lo = g->clean;
    if (lo < 25) return M_SAD;
    if (g->food > 65 && g->joy > 65 && g->clean > 65 && g->energy > 40) return M_HAPPY;
    return M_IDLE;
}

Need g_need(const Gerald *g) {
    if (g->stage == G_EGG) return NEED_NONE;
    if (g->fainted) return NEED_FAINT;
    if (g->sleeping) return NEED_NONE;
    if (g->sick) return NEED_SICK;
    if (g->energy < 20) return NEED_SLEEP;
    if (g->food < 25) return NEED_FOOD;
    if (g->poops >= 2 || g->clean < 30) return NEED_POOP;
    if (g->joy < 25) return NEED_JOY;
    return NEED_NONE;
}

const char *g_stage_name(int stage) {
    static const char *n[] = {"EGG", "TADPOLE", "FROGLET", "FROG", "ELDER"};
    return (stage >= 0 && stage <= G_ELDER) ? n[stage] : "?";
}

// ---------------------------------------------------------------------------
static ActResult gate(const Gerald *g) {
    if (g->stage == G_EGG) return ACT_EGG;
    if (g->fainted) return ACT_FAINTED;
    if (g->sleeping) return ACT_SLEEPING;
    return ACT_OK;
}

ActResult g_feed_meal(Gerald *g) {
    ActResult r = gate(g);
    if (r) return r;
    if (g->food >= 95) return ACT_FULL;
    g->food = clampf(g->food + 35, 0, 100);
    g->joy = clampf(g->joy + 3, 0, 100);
    g->meals++;
    if (g->poop_timer < 0) g->poop_timer = 900.0f + 900.0f * rnd01(g);   // 15-30 min
    return ACT_OK;
}

ActResult g_feed_snack(Gerald *g) {
    ActResult r = gate(g);
    if (r) return r;
    if (g->food >= 98) return ACT_FULL;
    g->food = clampf(g->food + 12, 0, 100);
    g->joy = clampf(g->joy + 14, 0, 100);
    g->snacks++;
    g->snack_load += 1.0f;
    if (g->poop_timer < 0 && rnd01(g) < 0.4f) g->poop_timer = 1200.0f;
    if (g->snack_load >= 4.0f && rnd01(g) < 0.5f) {
        g->sick = 1;
        g->snack_load = 0;
        return ACT_TUMMY_ACHE;
    }
    return ACT_OK;
}

ActResult g_clean(Gerald *g) {
    ActResult r = gate(g);
    if (r) return r;
    if (g->poops == 0 && g->clean >= 95) return ACT_ALREADY_CLEAN;
    g->poops = 0;
    g->clean = 100;
    g->joy = clampf(g->joy + 3, 0, 100);
    return ACT_OK;
}

ActResult g_toggle_lights(Gerald *g) {
    if (g->stage == G_EGG) return ACT_EGG;
    if (g->fainted) return ACT_FAINTED;
    if (g->sleeping) { g->sleeping = 0; return ACT_OK; }
    if (g->energy >= 90) return ACT_NOT_TIRED;
    g->sleeping = 1;
    return ACT_OK;
}

ActResult g_medicine(Gerald *g) {
    if (g->stage == G_EGG) return ACT_EGG;
    if (g->fainted) {
        g->fainted = 0;
        g->sick = 0;
        g->health = 40;
        g->food = g->food < 30 ? 30 : g->food;
        g->joy = g->joy < 30 ? 30 : g->joy;
        g->clean = g->clean < 30 ? 30 : g->clean;
        g->energy = g->energy < 30 ? 30 : g->energy;
        return ACT_REVIVED;
    }
    if (g->sleeping) return ACT_SLEEPING;
    if (!g->sick) return ACT_NOT_SICK;
    g->sick = 0;
    g->health = clampf(g->health + 15, 0, 100);
    g->joy = clampf(g->joy - 8, 0, 100);
    return ACT_OK;
}

ActResult g_can_play(const Gerald *g) {
    ActResult r = gate(g);
    if (r) return r;
    if (g->sick) return ACT_TOO_SICK;
    if (g->energy < 15) return ACT_TOO_TIRED;
    return ACT_OK;
}

void g_finish_game(Gerald *g, int score) {
    if (score < 0) score = 0;
    g->games_played++;
    g->flies_caught += (uint32_t)score;
    if ((uint32_t)score > g->best_score) g->best_score = (uint32_t)score;
    float j = 4.0f * score;
    g->joy = clampf(g->joy + (j > 45 ? 45 : j) + 4, 0, 100);
    float f = 1.5f * score;
    g->food = clampf(g->food + (f > 20 ? 20 : f), 0, 100);
    g->energy = clampf(g->energy - 12, 0, 100);
    g->clean = clampf(g->clean - 3, 0, 100);
}

void g_pet(Gerald *g) {
    if (g->stage == G_EGG || g->fainted || g->sleeping) return;
    g->joy = clampf(g->joy + 1.5f, 0, 100);
}
