ID=$RANDOM_$(date '+%Y_%m_%d_%H_%M_%S')

export RETRIEVAL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/retrieval_ip_$ID.txt
export PET_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_ip_$ID.txt
export MODEL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/model_ip_$ID.txt
export EMBED_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/embed_ip_$ID.txt

rm -f $RETRIEVAL_IP_PATH
rm -f $PET_IP_PATH
rm -f $MODEL_IP_PATH
rm -f $EMBED_IP_PATH

sbatch --export=ALL sglang.slurm
while [ ! -f "$MODEL_IP_PATH" ] || [ ! -f "$EMBED_IP_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for SGLang"
    sleep 20
done

sbatch --export=ALL pet.slurm
sbatch --export=ALL retrieval.slurm
while [ ! -f "$RETRIEVAL_IP_PATH" ] || [ ! -f "$PET_IP_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for retrieval and pet servers"
    sleep 20
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Everything ready."

sbatch --export=ALL agent.slurm

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent started."