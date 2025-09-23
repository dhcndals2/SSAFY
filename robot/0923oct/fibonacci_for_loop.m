function result=fibonacci_for_loop(n,threshold)

number=1;
curnumber=0;
beforenumber=0;

for i = 1:1:n

  if (i==1)
    curnumber=1;
  disp("1")

  elseif (i==2)
    beforenumber=1;
  disp("1")

  b =false;
  else
  number=curnumber+beforenumber;
  if(number>threshold&&!b)
  b=true;
  disp(["i'm ",num2str(i),"st       ",num2str(number) , " over!!!!!!!"])
  else
    disp(number)
  end
  beforenumber=curnumber;
  curnumber=number;
  end
end
