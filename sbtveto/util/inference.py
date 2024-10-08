import numpy as np
import torch
from torch_geometric.nn import knn
from torch_geometric.data import Data
from sbtveto.model.nn_model import NN
import joblib


def nn_output(model, data, scalar):
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    x = scalar.transform(data)
    x = torch.tensor(x, dtype =torch.float32 ).to(device)
    output = model(x)
    sbt_decision = (torch.max(output, dim = 1).indices != 0)#veto returns True if not signal(0)
    classification=torch.max(output, dim = 1).indices
    return output, sbt_decision,classification


def adjacency(n_dau):
    """ generates a fully connected adjacency
        for a mother to daughters """
    A=np.ones((n_dau+1, n_dau+1))
    return A


def gnn_output(model, x, sbt_xyz):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    device = 'cpu'
    j = 0
    X = np.vstack([np.expand_dims(x[:, :2000], 0), np.expand_dims(np.repeat(sbt_xyz[:1, :], x.shape[0], 0), 0),
                   np.expand_dims(np.repeat(sbt_xyz[1:2, :], x.shape[0], 0), 0),
                   np.expand_dims(np.repeat(sbt_xyz[2:, :], x.shape[0], 0), 0),
                   np.expand_dims(np.repeat(x[:, -4:-3], 2000, 1), 0),
                   np.expand_dims(np.repeat(x[:, -3:-2], 2000, 1), 0),
                   np.expand_dims(np.repeat(x[:, -2:-1], 2000, 1), 0),
                   np.expand_dims(np.repeat(x[:, -1:], 2000, 1), 0)])
    X = np.swapaxes(X, 0, 1)
    X = np.swapaxes(X, 1, 2)
    XSBT = X[:, :, :4].copy()

    X_UBT_sigvertex = X[:, 0, -3:].copy()[0]
    Xcon = XSBT[0][XSBT[0][:, 0] > 0]
    print(X_UBT_sigvertex.shape)
    print(Xcon.shape)

    Xcon = np.hstack([Xcon, np.expand_dims(np.arctan(Xcon[:, 2] / Xcon[:, 1]), 1)])
    if Xcon.shape[0] < 1:
        print("Less than one SBT cell gnn veto not possible. Therefore, using nn.")
        scaler_loaded = joblib.load('data/robust_scaler.pkl')
        nn = NN(2003, 3, [32, 32, 32, 16, 8], dropout=0)
        nn.load_model('data/SBTveto_vacuum_multiclass_NN_SBT_E_signal_xyz.pth')
        nn.eval()  # Set the model to evaluation mode
        return nn_output(nn, x, scaler_loaded)


    Xcon2 = torch.tensor(Xcon, dtype=torch.float)
    # if less than 22 SBT cells use a full connected graph
    if Xcon.shape[0] < 22:
        A = adjacency(Xcon.shape[0] - 1)
        tensor_edge_index = torch.tensor(A, dtype=torch.float).nonzero().t().contiguous()
    else:
        k = 5
        # perform k nearest neighbours clustering
        assign_index = knn(Xcon2, Xcon2, k)
        assign_index = assign_index
        assign_index = assign_index[:, assign_index[0] != assign_index[1]]
        tensor_edge_index = assign_index
    edge_index = tensor_edge_index.numpy()
    if edge_index.shape[1] == 0:
        print(edge_index.shape)


    r = torch.tensor(np.sqrt(np.sum((Xcon[edge_index[0], 1:4] - Xcon[edge_index[1], 1:4]) ** 2, 1)),
                         dtype=torch.float)
    delta_z = torch.tensor(Xcon[edge_index[0], 3] - Xcon[edge_index[1], 3], dtype=torch.float)
    delta_phi = torch.tensor(np.arctan(Xcon[edge_index[0], 2] / Xcon[edge_index[0], 1]) - np.arctan(
        Xcon[edge_index[1], 2] / Xcon[edge_index[1], 1]), dtype=torch.float)
    edge_features = torch.vstack([r, delta_z, delta_phi])
    edge_features = edge_features.T
    global_features = np.hstack([X_UBT_sigvertex, np.array([Xcon.shape[0]])])
    global_features = torch.tensor(global_features, dtype=torch.float).unsqueeze(0)
    edgepos = torch.tensor([j] * edge_index[0].shape[0], dtype=torch.int64)
    Xcon = torch.tensor(Xcon, dtype=torch.float)
    graph = Data(nodes=Xcon, edge_index=tensor_edge_index, edges=edge_features, graph_globals=global_features,
                 edgepos=edgepos)
    #graph
    graph['receivers'] = graph.edge_index[1]
    graph['senders'] = graph.edge_index[0]
    graph['edgepos'] = graph['edgepos'] - torch.min(graph['edgepos'])
    graph.batch = torch.zeros(graph.nodes.shape[0], dtype=torch.int64)

    # load model weights in here need to improve this
    model(graph.clone().detach())
    if device == 'cpu':
        model.load_state_dict(torch.load('data/SBT_vacuum_multiclass_4block_GNN_noUBT.pt', weights_only=True,
                                         map_location=torch.device('cpu')))
    else:
        model.load_state_dict(torch.load('data/SBT_vacuum_multiclass_4block_GNN_noUBT.pt', weights_only=True))
    model.eval()
    graph.to(device)
    model.to(device)
    output_graph = model(graph)

    sbt_decision = (torch.max(output_graph.graph_globals, dim = 1).indices != 0)#veto returns True if not signal(0)

    classification = torch.max(output_graph.graph_globals, dim = 1).indices
    return output_graph.graph_globals, sbt_decision, classification

