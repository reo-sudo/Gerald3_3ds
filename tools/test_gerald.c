// Host-side test for the pet simulation:  cc -Wall -Wextra -O1 -Isource tools/test_gerald.c source/gerald.c -o /tmp/test_gerald && /tmp/test_gerald
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "gerald.h"

#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static int fails;

static void hatch(Gerald *g) { g_step(g, 50, 1.0); }

int main(void) {
    Gerald g;
    // --- egg hatches after ~45 s
    g_new(&g, 1000);
    CHECK(g.stage == G_EGG);
    CHECK(g_feed_meal(&g) == ACT_EGG);
    CHECK(g_step(&g, 30, 1) == 0 && g.stage == G_EGG);
    CHECK((g_step(&g, 20, 1) & EV_HATCHED) && g.stage == G_TADPOLE);

    // --- growth by age
    g_new(&g, 0); hatch(&g);
    uint32_t ev = g_skip(&g, 4 * 3600 + 5);
    CHECK(g.stage == G_FROGLET); CHECK(ev & EV_EVOLVED);
    g_skip(&g, 20 * 3600);  CHECK(g.stage == G_FROG);
    g_skip(&g, 4 * 24 * 3600); CHECK(g.stage == G_ELDER);

    // --- total neglect: Gerald faints (and does NOT die), medicine revives
    g_new(&g, 0); hatch(&g);
    double t = 0; bool fainted = false;
    while (t < 48 * 3600) { if (g_step(&g, 20, 1) & EV_FAINTED) { fainted = true; break; } t += 20; }
    printf("neglect: fainted after %.1f h\n", t / 3600);
    CHECK(fainted && t > 4 * 3600 && t < 24 * 3600);
    CHECK(g_mood(&g) == M_FAINT);
    CHECK(g_feed_meal(&g) == ACT_FAINTED);
    CHECK(g_medicine(&g) == ACT_REVIVED);
    CHECK(!g.fainted && g.health > 0 && g_mood(&g) != M_FAINT);

    // --- diligent care keeps him healthy for 3 days
    g_new(&g, 0); hatch(&g);
    int faints = 0, sicks = 0;
    for (int step = 0; step < 3 * 24 * 60; step++) {      // one minute per step
        uint32_t e = g_step(&g, 60, 1);
        if (e & EV_FAINTED) faints++;
        if (e & EV_SICK) sicks++;
        if (g.food < 50) g_feed_meal(&g);
        if (g.poops) g_clean(&g);
        if (g.sick) g_medicine(&g);
        if (g.joy < 50) { g_can_play(&g) == ACT_OK ? g_finish_game(&g, 6) : (void)g_feed_snack(&g); }
        if (g.energy < 30 && !g.sleeping) g_toggle_lights(&g);
    }
    printf("care: faints=%d sicks=%d food=%.0f joy=%.0f clean=%.0f energy=%.0f health=%.0f stage=%s meals=%u\n",
           faints, sicks, g.food, g.joy, g.clean, g.energy, g.health, g_stage_name(g.stage), g.meals);
    CHECK(faints == 0); CHECK(g.health > 60);

    // --- actions
    g_new(&g, 0); hatch(&g);
    g.food = 96; CHECK(g_feed_meal(&g) == ACT_FULL);
    g.food = 40; CHECK(g_feed_meal(&g) == ACT_OK && g.food > 74 && g.poop_timer > 0);
    CHECK(g_clean(&g) == ACT_ALREADY_CLEAN);
    g.poops = 2; g.clean = 50; CHECK(g_clean(&g) == ACT_OK && g.poops == 0 && g.clean == 100);
    CHECK(g_medicine(&g) == ACT_NOT_SICK);
    g.energy = 95; CHECK(g_toggle_lights(&g) == ACT_NOT_TIRED);
    g.energy = 40; CHECK(g_toggle_lights(&g) == ACT_OK && g.sleeping);
    CHECK(g_feed_meal(&g) == ACT_SLEEPING);
    g_step(&g, 3600, 1);  CHECK(g.energy > 80);
    ev = g_step(&g, 3600, 1); CHECK(!g.sleeping); (void)ev;
    g.energy = 10; CHECK(g_can_play(&g) == ACT_TOO_TIRED);
    g.energy = 80; g.sick = 1; CHECK(g_can_play(&g) == ACT_TOO_SICK); g.sick = 0;
    CHECK(g_can_play(&g) == ACT_OK);
    float j = g.joy = 20; g_finish_game(&g, 5); CHECK(g.joy > j && g.best_score == 5 && g.flies_caught == 5);

    // poop appears after a meal
    g_new(&g, 0); hatch(&g); g.food = 10; g_feed_meal(&g);
    g_step(&g, 1900, 1); CHECK(g.poops == 1);

    // snack spam -> tummy ache eventually
    g_new(&g, 0); hatch(&g); int ache = 0;
    for (int i = 0; i < 40; i++) { g.food = 10; if (g_feed_snack(&g) == ACT_TUMMY_ACHE) ache++; }
    CHECK(ache > 0);

    // --- offline catch-up: 8 h asleep is fine, 3 days away ages him but is survivable math
    g_new(&g, 0); hatch(&g); g.energy = 20; g_toggle_lights(&g);
    g.last_time = 0; g_catchup(&g, 8 * 3600);
    printf("offline 8h asleep: food=%.0f joy=%.0f energy=%.0f health=%.0f sleeping=%d\n", g.food, g.joy, g.energy, g.health, g.sleeping);
    CHECK(!g.fainted);
    g_new(&g, 0); hatch(&g); g.last_time = 0;
    g_catchup(&g, 3 * 24 * 3600);
    printf("offline 3 days awake: stage=%s age=%.1fh fainted=%d\n", g_stage_name(g.stage), g.age / 3600, g.fainted);
    CHECK(!g.fainted && g.food < 20);                     // offline is gentle: hungry, not fainted...
    CHECK(g.age > 70 * 3600 && g.stage == G_FROG);        // ...and he kept growing up
    CHECK(g_catchup(&g, -50) == 0);                       // clock going backwards is ignored

    // --- save / load round trip + corruption detection
    g_new(&g, 12345); hatch(&g); g.meals = 7; g.food = 33.5f;
    CHECK(g_save(&g, "/tmp/gerald_test.sav"));
    Gerald h; memset(&h, 0, sizeof h);
    CHECK(g_load(&h, "/tmp/gerald_test.sav"));
    CHECK(h.meals == 7 && h.food == 33.5f && h.stage == G_TADPOLE);
    FILE *f = fopen("/tmp/gerald_test.sav", "r+b"); fseek(f, 20, SEEK_SET); fputc(0x7f, f); fclose(f);
    CHECK(!g_load(&h, "/tmp/gerald_test.sav"));
    CHECK(!g_load(&h, "/tmp/does_not_exist.sav"));

    // --- moods
    g_new(&g, 0); hatch(&g);
    CHECK(g_mood(&g) == M_HAPPY);
    g.joy = 10; CHECK(g_mood(&g) == M_SAD && g_need(&g) == NEED_JOY);
    g.food = 10; CHECK(g_need(&g) == NEED_FOOD);
    g.sick = 1; CHECK(g_mood(&g) == M_SICK && g_need(&g) == NEED_SICK);

    printf(fails ? "\n%d FAILURES\n" : "\nall tests passed\n", fails);
    return fails != 0;
}
