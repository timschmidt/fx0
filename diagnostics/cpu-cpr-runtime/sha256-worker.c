// SPDX-License-Identifier: MIT
// Bounded checksum load; changes only this process's CPU affinity.
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef FX0_LOAD_SECONDS
#define FX0_LOAD_SECONDS 30
#endif
#define BLOB_BYTES 1048576
static unsigned char blob[BLOB_BYTES];
static const uint32_t constants[64] = {
	0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
	0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
	0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
	0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
	0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
	0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
	0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
	0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
static uint32_t rotate(uint32_t x, unsigned int n)
{
	return (x >> n) | (x << (32 - n));
}
static void block(uint32_t h[8], const unsigned char data[64])
{
	uint32_t w[64],a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],v=h[7];
	for (unsigned int i=0; i<16; i++)
		w[i]=(uint32_t)data[4*i]<<24 | (uint32_t)data[4*i+1]<<16 |
		     (uint32_t)data[4*i+2]<<8 | data[4*i+3];
	for (unsigned int i=16; i<64; i++) {
		uint32_t s0=rotate(w[i-15],7)^rotate(w[i-15],18)^(w[i-15]>>3);
		uint32_t s1=rotate(w[i-2],17)^rotate(w[i-2],19)^(w[i-2]>>10);
		w[i]=w[i-16]+s0+w[i-7]+s1;
	}
	for (unsigned int i=0; i<64; i++) {
		uint32_t s1=rotate(e,6)^rotate(e,11)^rotate(e,25);
		uint32_t choice=(e&f)^(~e&g);
		uint32_t t1=v+s1+choice+constants[i]+w[i];
		uint32_t s0=rotate(a,2)^rotate(a,13)^rotate(a,22);
		uint32_t majority=(a&b)^(a&c)^(b&c);
		v=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+s0+majority;
	}
	h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=v;
}
static void checksum(const unsigned char *data, size_t length, char hex[65])
{
	uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
		      0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
	unsigned char tail[128]={0};
	size_t full=length&~(size_t)63,remaining=length-full;
	uint64_t bits=(uint64_t)length*8;
	for (size_t i=0; i<full; i+=64) block(h,data+i);
	memcpy(tail,data+full,remaining);tail[remaining]=0x80;
	size_t final_bytes=remaining<56?64:128;
	for (unsigned int i=0; i<8; i++) tail[final_bytes-1-i]=(unsigned char)(bits>>(8*i));
	block(h,tail);
	if (final_bytes==128) block(h,tail+64);
	for (unsigned int i=0; i<8; i++)
		for (unsigned int j=0; j<8; j++) hex[8*i+j]="0123456789abcdef"[(h[i]>>(28-4*j))&15];
	hex[64]=0;
}
static long number(const char *text, long maximum)
{
	char *end;
	if (!*text || *text<'0' || *text>'9') return -1;
	errno=0;
	long value=strtol(text,&end,10);
	return errno || *end || value<0 || value>maximum ? -1 : value;
}
static int milliseconds(clockid_t clock, uint64_t *result)
{
	struct timespec now;
	if (clock_gettime(clock,&now) || now.tv_sec<0 || now.tv_nsec<0 || now.tv_nsec>=1000000000) return -1;
	*result=(uint64_t)now.tv_sec*1000+(uint64_t)now.tv_nsec/1000000;
	return 0;
}
int main(int argc, char **argv)
{
	char digest[65];
	for (unsigned int i=0; i<BLOB_BYTES; i++) blob[i]=(unsigned char)i;
	if (argc==3 && !strcmp(argv[1],"--digest")) {
		long size=number(argv[2],BLOB_BYTES);
		if (size<0) return 2;
		checksum(blob,(size_t)size,digest);puts(digest);return 0;
	}
	if (argc!=3 || strcmp(argv[1],"--worker")) return 2;
	long cpu=number(argv[2],CPU_SETSIZE-1);
	if (cpu<0) return 2;
	cpu_set_t wanted,actual;
	CPU_ZERO(&wanted);CPU_SET(cpu,&wanted);
	if (sched_setaffinity(0,sizeof(wanted),&wanted) ||
	    sched_getaffinity(0,sizeof(actual),&actual) || !CPU_EQUAL(&wanted,&actual)) {
		perror("worker affinity");return 1;
	}
	uint64_t start,now,cpu_start,cpu_end;
	unsigned long hashes=0;
	if (milliseconds(CLOCK_MONOTONIC,&start) || milliseconds(CLOCK_PROCESS_CPUTIME_ID,&cpu_start)) return 1;
	do {
		/* Require a fresh read of the buffer on every iteration. */
		__asm__ volatile("" : : "r"(blob) : "memory");
		checksum(blob,BLOB_BYTES,digest);
		if (strcmp(digest,"fbbab289f7f94b25736c58be46a994c441fd02552cc6022352e3d86d2fab7c83")) {
			fputs("worker checksum mismatch\n",stderr);return 1;
		}
		hashes++;
		if (milliseconds(CLOCK_MONOTONIC,&now) || now<start) return 1;
	} while (now-start < (uint64_t)FX0_LOAD_SECONDS*1000);
	if (milliseconds(CLOCK_PROCESS_CPUTIME_ID,&cpu_end) || cpu_end<cpu_start ||
	    sched_getaffinity(0,sizeof(actual),&actual) || !CPU_EQUAL(&wanted,&actual)) return 1;
	printf("CPR_LOAD_WORKER cpu=%ld hashes=%lu bytes_per_hash=%u cpu_ms=%llu wall_ms=%llu affinity=%ld\n",
	       cpu,hashes,BLOB_BYTES,(unsigned long long)(cpu_end-cpu_start),(unsigned long long)(now-start),cpu);
	return 0;
}
