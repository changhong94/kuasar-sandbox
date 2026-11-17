import requests,json,time
s=requests.Session();t=s.get('https://auth.docker.io/token',params={'service':'registry.docker.io','scope':'repository:library/node:pull'},timeout=30).json()['token']
u='https://registry-1.docker.io/v2/library/node/blobs/sha256:0c4023204e5b4bcd551170279c40ff58285cc8ea87ddf9ff25cb3713e6ecda79'
r=s.get(u,headers={'Authorization':'Bearer '+t,'Range':'bytes=0-1023'},stream=True,timeout=30)
print(json.dumps({'status':r.status_code,'range':r.headers.get('Content-Range'),'length':r.headers.get('Content-Length')}),flush=True);r.close()
