# Local Kubernetes: Colima + kind

A self-contained Kubernetes environment with no Docker Desktop dependency.
Create throwaway clusters, deploy to them, tear them down.

## How the pieces fit

```
macOS host
  docker CLI ─┐
  kubectl ────┤
  kind ───────┘
        │
        ▼
  ┌─────────────────────────────────────────────┐
  │ Colima VM (Virtualization.framework)        │
  │   dockerd                                   │
  │     └── container: dev-control-plane        │  ← one kind cluster
  │           apiserver · etcd · scheduler      │
  │           your pods                         │
  └─────────────────────────────────────────────┘
```

| Tool | Role |
|---|---|
| `colima` | Runs a Linux VM containing `dockerd`. Replaces Docker Desktop. |
| `docker` | CLI only. Talks to whichever daemon the current context points at. |
| `kind` | Runs a whole Kubernetes control plane inside one Docker container. |
| `kubectl` | Talks to the cluster inside that container. |

The dependency is one-directional: **Colima must be running before kind can do
anything.** kind is not a runtime; it needs a Docker daemon underneath.

## Install

### macOS

Everything is pinned in `packages/Brewfile`, so a provisioned machine already
has it:

```sh
brew bundle install --file=packages/Brewfile
```

Or individually:

```sh
brew install colima docker kind kubernetes-cli
```

`docker` here is the CLI only - the Brewfile deliberately does **not** use
`link: false`, so the CLI comes from Homebrew rather than the Docker Desktop
app bundle. That is what makes the setup independent of Docker Desktop.

### Gotcha: Docker Desktop shadows kubectl

Docker Desktop's installer writes a root-owned `kubectl` to
`/usr/local/bin/kubectl`. Homebrew cannot symlink over it, so `brew install
kubernetes-cli` silently leaves you on Docker Desktop's older build. Check:

```sh
kubectl version --client        # Docker Desktop's is usually well behind
brew bundle check --file=packages/Brewfile --verbose | grep kubernetes-cli
```

If it reports `needs to be linked`:

```sh
sudo rm /usr/local/bin/kubectl
brew link --overwrite kubernetes-cli
```

### Linux (Ubuntu / Fedora / Pi)

**Colima is not needed.** Docker runs natively, so kind talks to the system
daemon directly. Install Docker via your distro, then add yourself to the
`docker` group. Neither `kubectl` nor `kind` is in the default apt/dnf repos:

```sh
# kubectl - see https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/
# kind
[ "$(uname -m)" = aarch64 ] && a=arm64 || a=amd64
curl -Lo ./kind "https://kind.sigs.k8s.io/dl/latest/kind-linux-$a"
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
```

The shell aliases below work on any OS; only the runtime layer differs.

## First-time Colima setup

Size the VM once. Settings persist, so later you just run `colima start`.

```sh
colima start --cpu 4 --memory 4 --disk 60
```

### Why 4 CPUs, not 2

This was tested directly, not guessed:

| VM size | Result |
|---|---|
| 2 CPU / 4 GB | **Fails.** `kubeadm` never finishes; no kubeconfig written. |
| 4 CPU / 4 GB | Works. Cluster ready in ~1m26s. |

At 2 vCPUs the etcd writes ran 100-400 ms against a 100 ms budget and the
apiserver missed its 10s startup deadline. Kubernetes wants 2 CPUs for the
control plane *alone*, before the OS and containerd take a share.

Memory at 4 GB was comfortable - 3.1 GB still free with a cluster running and
no OOM kills. Raise it if you run heavier workloads:

```sh
colima stop && colima start --cpu 4 --memory 8
```

Optional, start Colima at login:

```sh
brew services start colima
```

## Daily workflow

```sh
colima start                   # once per boot, ~20s

kindc --name dev               # create cluster, ~90s
kubectl get nodes              # context is switched for you, to kind-dev

# build/test loop
docker build -t myapp:dev .
kindi myapp:dev --name dev     # load image into the cluster, ~4s
kubectl rollout restart deploy/myapp

kpf svc/myapp 8080:80          # reach it at localhost:8080

kindd --name dev               # delete cluster
colima stop                    # optional, reclaims the VM's RAM
```

Two things that catch people out:

- **The node reports `NotReady` for the first ~60s.** Normal - the CNI pods are
  still starting. Use `kubectl wait --for=condition=Ready node --all
  --timeout=180s` if scripting.
- **A kind cluster cannot see your host's images.** You must `kind load
  docker-image` them in. Use a real tag like `myapp:dev`, never `:latest` -
  with `:latest` Kubernetes defaults to `imagePullPolicy: Always` and pulls
  from Docker Hub, ignoring the image you just loaded.

## Aliases

Defined in `zsh/.zshrc`. `k` tab-completes exactly like `kubectl`.

| Alias | Expands to |
|---|---|
| `kindc` | `kind create cluster` |
| `kindd` | `kind delete cluster` |
| `kindl` | `kind get clusters` |
| `kindi` | `kind load docker-image` |
| `k` | `kubectl` |
| `kg` | `kubectl get` |
| `kgp` `kgs` `kgd` `kgn` | `kubectl get` pods / svc / deploy / nodes |
| `kga` | `kubectl get all` |
| `kd` | `kubectl describe` |
| `kl` `klf` | `kubectl logs` / `logs -f` |
| `kex` | `kubectl exec -it` |
| `kaf` `kdf` | `kubectl apply -f` / `delete -f` |
| `kpf` | `kubectl port-forward` |
| `kev` | `kubectl get events`, time sorted |
| `kctx` `kctxl` | use-context / get-contexts |
| `kns` | set default namespace |

## Troubleshooting

**"Cannot connect to the Docker daemon"**

Colima is not running, or the Docker context is wrong.

```sh
colima status
colima start
docker context ls               # the * should be on "colima"
docker context use colima
```

**Cluster creation fails or hangs**

Almost always resources. Confirm the VM has what you think:

```sh
colima ssh -- nproc             # expect 4
colima ssh -- free -m           # expect ~3900 total
```

To see the real error instead of a Go stack trace, keep the failed node and
read its logs:

```sh
kind create cluster --name dev --retain
docker exec dev-control-plane journalctl -u kubelet --no-pager | tail -40
```

**A newly built image is not being used**

In order of likelihood: you forgot `kindi`; you used a `:latest` tag so
Kubernetes pulled from the registry; or the old pods are still running and
need `kubectl rollout restart`. Confirm the image reached the node:

```sh
docker exec dev-control-plane crictl images | grep myapp
```

**Exposing a fixed host port instead of port-forwarding**

Port mappings must be declared at cluster creation time:

```yaml
# kind-dev.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8080
```

```sh
kind create cluster --name dev --config kind-dev.yaml
```

Expose the service as a NodePort on 30080; reach it at `localhost:8080`.

**Going back to Docker Desktop**

It is still installed, just unused. Start the app, then:

```sh
docker context use desktop-linux   # docker context use colima to come back
```

## Reclaiming disk

```sh
kind get clusters                  # delete any you forgot about
docker system prune -a             # images and build cache inside the VM
colima delete                      # nuke the VM entirely; recreate with colima start
```
