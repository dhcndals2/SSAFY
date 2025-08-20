#define _CRT_SECURE_NO_WARNINGS
#include <iostream>
#include <queue>

using namespace std;

int dy[] = { -1,1,0,0 };
int dx[] = { 0,0,-1,1 };

struct Edge
{
	int y;
	int x;
	int cost;
	int height;
};

struct cmp
{
	bool operator()(Edge a, Edge b)
	{
		return a.height > b.height;
	}
};
int n;
int map[100][100];
int dist[100][100];

void dijkstra(Edge st)
{
	priority_queue<Edge, vector<Edge>, cmp> pq;
	pq.push({ st });
	dist[st.y][st.x] = st.cost;
	while (!pq.empty())
	{
		Edge cp = pq.top();
		pq.pop();
		
		if (dist[cp.y][cp.x] < cp.cost)
			continue;

		for (int i = 0; i < 4; i++)
		{
			Edge np;
			np.y = cp.y + dy[i];
			np.x = cp.x + dx[i];
			if (np.y < 0 || np.x < 0 || np.y >= n || np.x >= n)
				continue;
			np.height = map[np.y][np.x];
			if (np.height > cp.height)
			{
				np.cost = cp.cost + (np.height - cp.height) * 2;
			}
			else if (np.height == cp.height)
			{
				np.cost = cp.cost + 1;
			}
			else
				np.cost = cp.cost;

			if (np.cost < dist[np.y][np.x])
			{
				dist[np.y][np.x] = np.cost;
				pq.push({ np.y,np.x,np.cost,np.height});
			}
		}
	}
}

int main()
{
	int t;
	cin >> t;
	for(int test=0;test<t;test++)
	{
	// freopen("input.txt", "r", stdin);
	cin >> n;
	for (int i = 0; i < n; i++)
	{
		for (int j = 0; j < n; j++)
		{
			cin >> map[i][j];
		}
	}
	for (int i = 0; i < n; i++)
	{
		for(int j=0;j< n;j++)
		{ 
			dist[i][j] = 21e8;
		}
	}
	Edge st;
	st.y = 0;
	st.x = 0;
	st.cost = 0;
	st.height = map[st.y][st.x];
	dijkstra(st);
	cout << "#" << test + 1 << " " << dist[n - 1][n - 1] << endl;
	}
	return 0;

}
