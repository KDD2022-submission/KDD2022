import tensorflow as tf
from utility.helper import *
from utility.batch_test import *
from time import time

from BPRMF import BPRMF
from FENDER import FENDER


import os
import sys
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

def load_pretrained_data(args):
    pre_model = 'mf'
    if args.pretrain == -2:
        pre_model = 'kgat'
    pretrain_path = '%spretrain/%s/%s.npz' % (args.proj_path, args.dataset, pre_model)
    try:
        pretrain_data = np.load(pretrain_path)
        print('load the pretrained bprmf model parameters.')
    except Exception:
        pretrain_data = None
    return pretrain_data


if __name__ == '__main__':
    # get argument settings.
    tf.set_random_seed(2021)
    np.random.seed(2021)
    args = parse_args()

    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)

    """
    *********************************************************
    Load Data from data_generator function.
    """
    config = dict()
    config['n_users'] = data_generator.n_users
    config['n_items'] = data_generator.n_items

    t0 = time()

    """
    *********************************************************
    Use the pretrained data to initialize the embeddings.
    """
    if args.pretrain in [-1, -2]:
        pretrain_data = load_pretrained_data(args)
    else:
        pretrain_data = None

    """
    *********************************************************
    Select one of the models.
    """
    if args.model_type == 'fender':
        model = FENDER(data_config=config, pretrain_data=pretrain_data, args=args)
    if args.model_type == 'bprmf':
        model = BPRMF(data_config=config, pretrain_data=pretrain_data, args=args)

    saver = tf.train.Saver()

    """
    *********************************************************
    Save the model parameters.
    """
    
    weights_save_path = '%sweights/%s/%s/l%s_r%s' % (args.weights_path, args.dataset, model.model_type,
                                                             str(args.lr), '-'.join([str(r) for r in eval(args.regs)]))

        

    ensureDir(weights_save_path)
    save_saver = tf.train.Saver(max_to_keep=1)

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.Session(config=config)

    """
    *********************************************************
    Reload the model parameters to fine tune.
    """
    if args.pretrain == 1:
        
        pretrain_path = '%sweights/%s/%s/l%s_r%s' % (args.weights_path, args.dataset, model.model_type, str(args.lr),
                                                             '-'.join([str(r) for r in eval(args.regs)]))

        ckpt = tf.train.get_checkpoint_state(os.path.dirname(pretrain_path + '/checkpoint'))
        if ckpt and ckpt.model_checkpoint_path:
            sess.run(tf.global_variables_initializer())
            saver.restore(sess, ckpt.model_checkpoint_path)
            print('load the pretrained model parameters from: ', pretrain_path)

            # *********************************************************
            # get the performance from the model to fine tune.
            if args.report != 1:
                users_to_test = list(data_generator.test_user_dict.keys())

                ret = test(sess, model, users_to_test, drop_flag=False, batch_test_flag=batch_test_flag)
                cur_best_pre_0 = ret['recall'][0]

                pretrain_ret = 'pretrained model hit=[%.5f, %.5f],' \
                               'ndcg=[%.5f, %.5f], nTFR=[%.5f, %.5f]' % \
                               (ret['hit_ratio'][0], ret['hit_ratio'][-1],
                                ret['ndcg'][0], ret['ndcg'][-1],
                                ret['nTFR'][0], ret['nTFR'][-1])
                print(pretrain_ret)

                # *********************************************************
                # save the pretrained model parameters of mf (i.e., only user & item embeddings) for pretraining other models.
                if args.save_flag == -1:
                    user_embed, item_embed = sess.run(
                        [model.weights['user_embedding'], model.weights['item_embedding']],
                        feed_dict={})
                    # temp_save_path = '%spretrain/%s/%s/%s_%s.npz' % (args.proj_path, args.dataset, args.model_type, str(args.lr),
                    #                                                  '-'.join([str(r) for r in eval(args.regs)]))
                    temp_save_path = '%spretrain/%s/%s.npz' % (args.proj_path, args.dataset, model.model_type)
                    ensureDir(temp_save_path)
                    np.savez(temp_save_path, user_embed=user_embed, item_embed=item_embed)
                    print('save the weights of fm in path: ', temp_save_path)
                    exit()

                # *********************************************************
                # save the pretrained model parameters of kgat (i.e., user & item & kg embeddings) for pretraining other models.
                if args.save_flag == -2:
                    user_embed, entity_embed, relation_embed = sess.run(
                        [model.weights['user_embed'], model.weights['entity_embed'], model.weights['relation_embed']],
                        feed_dict={})

                    temp_save_path = '%spretrain/%s/%s.npz' % (args.proj_path, args.dataset, args.model_type)
                    ensureDir(temp_save_path)
                    np.savez(temp_save_path, user_embed=user_embed, entity_embed=entity_embed, relation_embed=relation_embed)
                    print('save the weights of kgat in path: ', temp_save_path)
                    exit()

        else:
            sess.run(tf.global_variables_initializer())
            cur_best_pre_0 = 0.
            print('without pretraining.')
    else:
        sess.run(tf.global_variables_initializer())
        cur_best_pre_0 = 0.
        print('without pretraining.')

    """
    *********************************************************
    Get the final performance w.r.t. different sparsity levels.
    """
    if args.report == 1:
        assert args.test_flag == 'full'
        users_to_test_list, split_state = data_generator.get_sparsity_split()

        users_to_test_list.append(list(data_generator.test_user_dict.keys()))
        split_state.append('all')

        save_path = '%sreport/%s/%s.result' % (args.proj_path, args.dataset, model.model_type)
        ensureDir(save_path)
        f = open(save_path, 'w')
        f.write('embed_size=%d, lr=%.4f, regs=%s, loss_type=%s, \n' % (args.embed_size, args.lr, args.regs,
                                                                       args.loss_type))

        for i, users_to_test in enumerate(users_to_test_list):
            ret = test(sess, model, users_to_test, drop_flag=False, batch_test_flag=batch_test_flag)

            final_perf = "hit=[%s], ndcg=[%s], nTFR=[%s]" % \
                         ('\t'.join(['%.5f' % r for r in ret['hit_ratio']]),
                          '\t'.join(['%.5f' % r for r in ret['ndcg']]),
                          '\t'.join(['%.5f' % r for r in ret['nTFR']]))
            print(final_perf)

            f.write('\t%s\n\t%s\n' % (split_state[i], final_perf))
        f.close()
        exit()

    """
    *********************************************************
    Train.
    """
    loss_loger, pre_loger, rec_loger, ndcg_loger, hit_loger, nTFR_loger = [], [], [], [], [], []
    stopping_step = 0
    should_stop = False

    for epoch in range(args.epoch):
        t1 = time()
        loss, base_loss, reg_loss = 0., 0., 0.
        n_batch = data_generator.n_train // args.batch_size + 1

        """
        *********************************************************
        ... phase 1: to train the recommender.
        """
        for idx in range(n_batch):
            btime= time()

            batch_data = data_generator.generate_train_batch()
            feed_dict = data_generator.generate_train_feed_dict(model, batch_data)

            _, batch_loss, batch_base_loss, batch_reg_loss = model.train(sess, feed_dict=feed_dict)

            loss += batch_loss
            base_loss += batch_base_loss
            reg_loss += batch_reg_loss

        if np.isnan(loss) == True:
            print('ERROR: loss@phase1 is nan.')
            sys.exit()


        if np.isnan(loss) == True:
            print('ERROR: loss@phase2 is nan.')
            sys.exit()

        show_step = 5
        if (epoch + 1) % show_step != 0:
            if args.verbose > 0 and epoch % args.verbose == 0:
                perf_str = 'Epoch %d [%.1fs]: train==[%.5f=%.5f + %.5f]' % (
                    epoch, time() - t1, loss, base_loss, reg_loss)
                print(perf_str)
            continue

        """
        *********************************************************
        Test.
        """
        t2 = time()
        users_to_test = list(data_generator.test_user_dict.keys())

        ret = test(sess, model, users_to_test, drop_flag=False, batch_test_flag=batch_test_flag)

        """
        *********************************************************
        Performance logging.
        """
        t3 = time()

        loss_loger.append(loss)
        ndcg_loger.append(ret['ndcg'])
        hit_loger.append(ret['hit_ratio'])
        nTFR_loger.append(ret['nTFR'])

        if args.verbose > 0:
            perf_str = 'Epoch %d [%.1fs + %.1fs]: train==[%.5f=%.5f + %.5f],' \
                       'hit=[%.5f, %.5f], ndcg=[%.5f, %.5f], nTFR=[%.5f, %.5f]' % \
                       (epoch, t2 - t1, t3 - t2, loss, base_loss, reg_loss, ret['hit_ratio'][0], ret['hit_ratio'][-1],
                        ret['ndcg'][0], ret['ndcg'][-1], ret['nTFR'][0], ret['nTFR'][-1])
            print(perf_str)
            

        # *********************************************************
        # early stopping when cur_best_pre_0 is decreasing for ten successive steps.
       
        # *********************************************************
        # save the user & item embeddings for pretraining.


