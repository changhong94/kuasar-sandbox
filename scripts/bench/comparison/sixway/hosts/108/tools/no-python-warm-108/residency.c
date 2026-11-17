#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
int main(int argc,char **argv){for(int i=1;i<argc;i++){int fd=open(argv[i],O_RDONLY);struct stat st;if(fd<0||fstat(fd,&st))return 2;size_t n=(st.st_size+4095)/4096;unsigned char *v=calloc(n,1);void *p=mmap(0,st.st_size,PROT_READ,MAP_PRIVATE,fd,0);if(p==MAP_FAILED||mincore(p,st.st_size,v))return 3;size_t r=0;for(size_t k=0;k<n;k++)r+=v[k]&1;printf("%s %zu %zu\n",argv[i],r,n);munmap(p,st.st_size);free(v);close(fd);}return 0;}
