#!/bin/bash
# SSH 비밀번호를 환경변수에서 주입 (미설정 시 기본값: root)
echo "root:${SSH_PASSWORD:-root}" | chpasswd
# sshd 데몬을 백그라운드로 시작
/usr/sbin/sshd
# 원래 CMD 또는 전달된 명령 실행
exec "$@"
