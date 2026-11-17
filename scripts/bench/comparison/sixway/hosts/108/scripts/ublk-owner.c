#include <linux/io_uring.h>
#include <linux/ublk_cmd.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv){
 if(argc!=2||strlen(argv[1])<6||strncmp(argv[1],"ublk",4)||!strchr("cb",argv[1][4]))return 1;
 char *end;long id=strtol(argv[1]+5,&end,10);if(*end||id<0||id>1048575)return 1;
 int dev=open("/dev/ublk-control",O_RDWR|O_CLOEXEC);if(dev<0)return 2;
 struct io_uring_params p={.flags=IORING_SETUP_SQE128};
 int fd=syscall(__NR_io_uring_setup,4,&p);if(fd<0)return 3;
 size_t sz=p.sq_off.array+p.sq_entries*sizeof(unsigned),cz=p.cq_off.cqes+p.cq_entries*sizeof(struct io_uring_cqe);
 if(p.features&IORING_FEAT_SINGLE_MMAP){if(cz>sz)sz=cz;}
 void *sq=mmap(0,sz,PROT_READ|PROT_WRITE,MAP_SHARED,fd,IORING_OFF_SQ_RING);if(sq==MAP_FAILED)return 4;
 void *cq=(p.features&IORING_FEAT_SINGLE_MMAP)?sq:mmap(0,cz,PROT_READ|PROT_WRITE,MAP_SHARED,fd,IORING_OFF_CQ_RING);if(cq==MAP_FAILED)return 5;
 struct io_uring_sqe *s=mmap(0,p.sq_entries*128,PROT_READ|PROT_WRITE,MAP_SHARED,fd,IORING_OFF_SQES);if(s==MAP_FAILED)return 6;
 struct ublksrv_ctrl_dev_info info={0};s->opcode=IORING_OP_URING_CMD;s->fd=dev;s->cmd_op=UBLK_U_CMD_GET_DEV_INFO;
 struct ublksrv_ctrl_cmd *c=(void*)s->cmd;c->dev_id=id;c->queue_id=UINT16_MAX;c->addr=(uintptr_t)&info;c->len=sizeof(info);
 *(unsigned*)(sq+p.sq_off.array)=0;__atomic_store_n((unsigned*)(sq+p.sq_off.tail),1,__ATOMIC_RELEASE);
 if(syscall(__NR_io_uring_enter,fd,1,1,IORING_ENTER_GETEVENTS,0,0)<0)return 7;
 struct io_uring_cqe *e=cq+p.cq_off.cqes;if(e->res<0)return 8;
 printf("%u\n",info.owner_uid);return 0;
}
