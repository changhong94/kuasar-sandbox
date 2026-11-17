#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1e6;}
int main(int argc,char **argv){if(argc<2)return 2;int f[2];if(pipe(f))return 3;double start=now(),first=-1;pid_t p=fork();if(p<0)return 4;if(!p){close(f[0]);if(dup2(f[1],1)<0)_exit(126);close(f[1]);execv(argv[1],argv+1);_exit(127);}close(f[1]);char b[4096];ssize_t n;while((n=read(f[0],b,sizeof b))>0){if(first<0)first=now()-start;ssize_t off=0;while(off<n){ssize_t k=write(1,b+off,n-off);if(k<0)return 5;off+=k;}}close(f[0]);int status;struct rusage u;if(wait4(p,&status,0,&u)<0)return 6;fprintf(stderr,"PROBE {\"first_stdout_ms\":%.6f,\"wall_ms\":%.6f,\"user_ms\":%.6f,\"system_ms\":%.6f,\"minor_faults\":%ld,\"major_faults\":%ld,\"block_input\":%ld,\"voluntary_switches\":%ld,\"involuntary_switches\":%ld}\n",first,now()-start,u.ru_utime.tv_sec*1000.0+u.ru_utime.tv_usec/1000.0,u.ru_stime.tv_sec*1000.0+u.ru_stime.tv_usec/1000.0,u.ru_minflt,u.ru_majflt,u.ru_inblock,u.ru_nvcsw,u.ru_nivcsw);return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);}
