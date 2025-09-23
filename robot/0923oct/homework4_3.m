clc;
clear;
close all;

load fruit_inventory.mat

bar(values);

grid on;

title('Fruit Sales');
ylabel('Quantity');
xlabel('Fruit Name');

xticklabels(categories);
