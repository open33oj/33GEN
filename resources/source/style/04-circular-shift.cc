#include<bits/stdc++.h>
using namespace std;
const int MAXN = 200000;
int n;
int a[MAXN+5],posA;
int b[MAXN+5],posB;
int main()
{
    cin>>n;
    for(int i=1;i<=n;i++)
    	cin>>a[i];
    for(int i=1;i<=n;i++)
    	cin>>b[i];
    
    for(int i=1;i<=n;i++)
    {
		if(a[i]==1) posA = i;
    	if(b[i]==1) posB = i;
    }
    int ans = abs(posA-posB);
    while(posA!=1)
    {
		swap(a[posA],a[posA-1]);
    	posA--;
    }
    while(posB!=1)
    {
		swap(b[posB],b[posB-1]);
    	posB--;
    }
    
    bool flag=true;
    for(int i=1;i<=n;i++)
    	if(a[i]!=b[i])
    	{
			flag=false;
    		break;
    	}
    
    if(!flag)
    	cout<<"No";
    else
    	cout<<"Yes\n"<<ans;
}
