clc;
clear;
close all;

##a=10;
##b=20;
##
##disp(a+b);
##disp(a-b);
##disp(a*b);
##disp(a/b);
##
##c=a*b+10
##d=(b-a)^2
##e=a*b/d
##f=(c^2+d*e-(a+b)^(1/2))/(a+b+c+d+e)
##
##number=input('input');
##
##if(number>0)
##  disp("양수");
##elseif(number==0)
##  disp('0');
##else
##  disp('음수');
##end

##for i = 1:1:100
##  disp(i)
##end
##n=0
##while n<50
## disp(n)
##  n=n+1;
##end

##n=input('input ')
##number=1;
##curnumber=0;
##beforenumber=0;
##
##for i = 1:1:n
##
##  if (i==1)
##    curnumber=1;
##  disp("1")
##
##  elseif (i==2)
##    beforenumber=1;
##  disp("1")
##
##  b =false;
##  else
##  number=curnumber+beforenumber;
##  if(number>1000&&!b)
##  b=true;
##  disp(["i'm",num2str(i),"st::::1000 over!!!!!!!"])
##  end
##  disp(number)
##  beforenumber=curnumber;
##  curnumber=number;
##  end
##end

##n = input('input ');
##number = 1;
##curnumber = 0;
##beforenumber = 0;
##b = false;
##i = 1;
##while (i <= n)
##  if (i == 1)
##    curnumber = 1;
##    disp("1")
##  elseif (i == 2)
##    beforenumber = 1;
##    disp("1")
##  else
##    number = curnumber + beforenumber;
##    if (number > 1000 && !b)
##      b = true;
##      disp(sprintf("i'm %d st::::1000 over!!!!!!!", i))
##    end
##    disp(number)
##    beforenumber = curnumber;
##    curnumber = number;
##  end
##  i = i + 1;
##end

number =square_number(5);
disp(number)

n=input('n`input :');
number = input("threshold` input");

fibonacci_for_loop(n,number)

n=input('n`input :');
number = input("threshold` input");

fibonacci_while_loop(n,number)




