# dojo

L'exécution d'une instance : passerelle de modèles (litellm), base
(postgres), chat (open-webui), proxy (caddy).

    cp .env.example .env      # renseigner ses clés — jamais commitées
    docker compose up -d

Les trois coches du démarrage sont dans le README racine. La configuration
des moteurs vit dans `litellm-config.yaml` : un modèle = un nom virtuel et
son incarnation, en placeholders IONOS AI Model Hub par défaut.
