
export RETRIEVAL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/retrieval_ip.txt
export PET_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/pet_ip.txt
export MODEL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/model_ip.txt
export EMBED_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/embed_ip.txt

rm -f $RETRIEVAL_IP_PATH
rm -f $PET_IP_PATH
rm -f $MODEL_IP_PATH
rm -f $EMBED_IP_PATH

sbatch --export=ALL pet.slurm
sbatch --export=ALL retrieval.slurm
sbatch --export=ALL sglang.slurm

while [ ! -f "$RETRIEVAL_IP_PATH" ] || [ ! -f "$PET_IP_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for retrieval and pet servers"
    sleep 20
done

while [ ! -f "$MODEL_IP_PATH" ] || [ ! -f "$EMBED_IP_PATH" ]; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for SGLang"
    sleep 20
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Everything ready."