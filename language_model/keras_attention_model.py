from __future__ import print_function

##############
# Make model #
##############
from keras.layers import Lambda, MaxPooling1D, Dense, Flatten, Dropout, Masking
from keras.optimizers import SGD

from language_model.word_embeddings import Word2VecEmbedding


def make_model(maxlen, n_words, n_lstm_dims=141, n_embed_dims=128):
    from keras.optimizers import RMSprop

    from language_model.attention_lstm import AttentionLSTM

    from keras.layers import Input, LSTM, merge
    from keras.models import Model
    import keras.backend as K

    # input
    question = Input(shape=(maxlen,), dtype='int32')
    answer_good = Input(shape=(maxlen,), dtype='int32')
    answer_bad = Input(shape=(maxlen,), dtype='int32')

    # language model
    embedding = Word2VecEmbedding('word2vec.model')

    # forward and backward lstms
    f_lstm = LSTM(n_lstm_dims, return_sequences=True)
    b_lstm = LSTM(n_lstm_dims, go_backwards=True, return_sequences=True)

    # Note: Change concat_axis to 2 if return_sequences=True

    # question part
    q_emb = embedding(question)
    q_fl = f_lstm(q_emb)
    q_bl = b_lstm(q_emb)
    q_out = merge([q_fl, q_bl], mode='concat', concat_axis=2)
    q_out = MaxPooling1D()(q_out)
    q_out = Flatten()(q_out)

    # forward and backward attention lstms (paying attention to q_out)
    f_lstm_attention = AttentionLSTM(n_lstm_dims, q_out, return_sequences=True)
    b_lstm_attention = AttentionLSTM(n_lstm_dims, q_out, go_backwards=True, return_sequences=True)

    # answer part
    ag_emb = embedding(answer_good)
    ag_fl = f_lstm_attention(ag_emb)
    ag_bl = b_lstm_attention(ag_emb)
    ag_out = merge([ag_fl, ag_bl], mode='concat', concat_axis=2)
    ag_out = MaxPooling1D()(ag_out)
    ag_out = Flatten()(ag_out)

    ab_emb = embedding(answer_bad)
    ab_fl = f_lstm_attention(ab_emb)
    ab_bl = b_lstm_attention(ab_emb)
    ab_out = merge([ab_fl, ab_bl], mode='concat', concat_axis=2)
    ab_out = MaxPooling1D()(ab_out)
    ab_out = Flatten()(ab_out)

    # merge together
    # note: `cos` refers to "cosine similarity", i.e. similar vectors should go to 1
    # for training's sake, "abs" limits range to be tween 0 and 1 (binary classification)
    good_out = merge([q_out, ag_out], name='good', mode='cos', dot_axes=1)
    bad_out = merge([q_out, ab_out], name='bad', mode='cos', dot_axes=1)

    target = merge([good_out, bad_out], name='target', mode=lambda x: K.maximum(0, 0.2 - x[0] + x[1]), output_shape=lambda x: x[0])

    model = Model(input=[question, answer_good, answer_bad], output=target)

    # need to choose binary crossentropy or mean squared error
    print('Compiling model...')

    optimizer = RMSprop(lr=0.0001)
    # optimizer = SGD(lr=0.001, momentum=0.9, nesterov=True)

    # this is more true to the paper: L = max{0, M - cosine(q, a+) + cosine(q, a-)}
    # below, "a" is a list of zeros and "b" is `target` above, i.e. 1 - cosine(q, a+) + cosine(q, a-)
    # loss = 'binary_crossentropy'
    # loss = 'mse'
    # loss = 'hinge'

    def loss(y_true, y_pred):
        return y_pred

    # unfortunately, the hinge loss approach means the "accura cy" metric isn't very valuable
    metrics = []

    model.compile(optimizer=optimizer, loss=loss, metrics=metrics)

    return model

if __name__ == '__main__':
    # get the data set
    maxlen = 100 # words

    from language_model.get_data import get_data_set, create_dictionary_from_qas

    dic = create_dictionary_from_qas()
    targets, questions, answers, n_dims = get_data_set(maxlen)

    ### THIS MODEL PERFORMS WELL ON THE TEST SET
    model = make_model(maxlen, n_dims)

    print('Fitting model')
    model.fit([questions, answers], targets, nb_epoch=5, batch_size=32, validation_split=0.2)
    model.save_weights('attention_lm_weights.h5', overwrite=True)
