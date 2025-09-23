clc;
clear;
close all;

A =[1,2,3;4,5,6;7,8,9]
B=[1,0,0;0,5,0;0,0,9]
C=[0,0,0;0,0,0]

K=[1,2,3;4,5,6;7,8,9]
G = [9,8,7;6,5,4;3,2,1]

K+G
K-G
K*G
K'
inv(G)


T1 = [1,0,0,2;0,1,0,3;0,0,1,4;0,0,0,1]
T2 =[0,-1,0,5;1,0,0,6;0,0,1,7;0,0,0,1]

T1+T2
T1-T2
T1*T2
T2'
inv(T2)

theta_a = 45 * pi / 180;

Rx_a = [1, 0, 0, 0;
        0, cos(theta_a), -sin(theta_a), 0;
        0, sin(theta_a), cos(theta_a), 0;
        0, 0, 0, 1];

Ry_a = [cos(theta_a), 0, sin(theta_a), 0;
        0, 1, 0, 0;
        -sin(theta_a), 0, cos(theta_a), 0;
        0, 0, 0, 1];
R_a = Rx_a * Ry_a

theta_b = pi / 6;

Rx_a = [1, 0, 0, 0;
        0, cos(theta_b), -sin(theta_b), 0;
        0, sin(theta_b), cos(theta_b), 0;
        0, 0, 0, 1];

Ry_a = [cos(theta_b), 0, sin(theta_b), 0;
        0, 1, 0, 0;
        -sin(theta_b), 0, cos(theta_b), 0;
        0, 0, 0, 1];
R_a = Rx_a * Ry_a


A=[1,2;3,4];
B=[0,1;-1,0];
C=[2,0;1,3];
D=[4,1;0,2];

K=[A,B;C,D]
inv(K)
