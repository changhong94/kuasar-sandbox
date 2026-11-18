#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

/* Application state stays in memory and is inherited by the live child. */
int main(void) {
    uint64_t counter = 0;
    struct timespec tick = {.tv_sec = 0, .tv_nsec = 10000000};
    for (;;) {
        struct timespec now;
        if (clock_gettime(CLOCK_MONOTONIC, &now)) return 1;
        printf("%d %llu %lld\n", getpid(), (unsigned long long)++counter,
               (long long)now.tv_sec * 1000000000LL + now.tv_nsec);
        if (fflush(stdout)) return 2;
        nanosleep(&tick, NULL);
    }
}
