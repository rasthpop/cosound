/**
 * Generated from frontend/openapi.json by scripts/contract.mjs (openapi-typescript).
 * Do not edit: change the backend DTOs, run `make contract`, then `npm run contract`.
 */

export interface paths {
    "/api/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Feedback */
        post: operations["submitFeedback"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Health */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/map/meta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Map Meta */
        get: operations["getMapMeta"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/map/points": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Map Points */
        get: operations["getMapPoints"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search */
        post: operations["search"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["getSession"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tracks/{track_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Track */
        get: operations["getTrack"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tracks/{track_id}/audio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Track Audio */
        get: operations["getTrackAudio"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tracks/{track_id}/neighbors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Neighbors */
        get: operations["getTrackNeighbors"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ApiWarning */
        ApiWarning: {
            /**
             * Code
             * @description e.g. `semantic_unavailable`, `llm_fallback`, `map_unavailable`
             */
            code: string;
            /** Message */
            message: string;
        };
        /** Artist */
        Artist: {
            /** Artist Id */
            artist_id: string;
            /** Name */
            name: string;
        };
        /** AudioInfo */
        AudioInfo: {
            /** Duration Seconds */
            duration_seconds: number | null;
            /** License */
            license: string | null;
        };
        /** Capabilities */
        Capabilities: {
            llm_interpreter: components["schemas"]["InterpreterStatus"];
            map: components["schemas"]["CapabilityStatus"];
            semantic: components["schemas"]["CapabilityStatus"];
        };
        /**
         * CapabilityStatus
         * @enum {string}
         */
        CapabilityStatus: "available" | "unavailable";
        /**
         * ConstraintAttribute
         * @enum {string}
         */
        ConstraintAttribute: "vocals" | "instrument" | "genre" | "era" | "tempo" | "duration";
        /** ConstraintCheck */
        ConstraintCheck: {
            attribute: components["schemas"]["ConstraintAttribute"];
            operator: components["schemas"]["ConstraintOperator"];
            status: components["schemas"]["ConstraintStatus"];
            /** Value */
            value: string | null;
        };
        /**
         * ConstraintOperator
         * @enum {string}
         */
        ConstraintOperator: "required" | "excluded" | "range";
        /**
         * ConstraintStatus
         * @enum {string}
         */
        ConstraintStatus: "satisfied" | "violated" | "unknown";
        /** ErrorBody */
        ErrorBody: {
            /**
             * Code
             * @description Stable machine code, e.g. `track_not_found`.
             */
            code: string;
            /**
             * Details
             * @default {}
             */
            details?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Message */
            message: string;
        };
        /**
         * ErrorResponse
         * @description The envelope of every non-2xx response.
         * @example {
         *       "error": {
         *         "code": "validation_error",
         *         "details": {
         *           "errors": [
         *             {
         *               "loc": "body.query",
         *               "msg": "too short"
         *             }
         *           ]
         *         },
         *         "message": "Request is invalid."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "track_not_found",
         *         "details": {
         *           "track_id": "trk_example_9"
         *         },
         *         "message": "Track trk_example_9 does not exist."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "session_not_found",
         *         "details": {
         *           "session_id": "ses_example_9"
         *         },
         *         "message": "Session ses_example_9 does not exist."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "track_not_in_results",
         *         "details": {
         *           "query_id": "qry_example_1",
         *           "track_id": "trk_example_9"
         *         },
         *         "message": "Track trk_example_9 was not returned for query qry_example_1."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "projection_unavailable",
         *         "details": {},
         *         "message": "The track map is not available."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "audio_missing",
         *         "details": {
         *           "track_id": "trk_example_3"
         *         },
         *         "message": "Track trk_example_3 has no validated audio."
         *       }
         *     }
         * @example {
         *       "error": {
         *         "code": "internal_error",
         *         "details": {},
         *         "message": "Something went wrong."
         *       }
         *     }
         */
        ErrorResponse: {
            error: components["schemas"]["ErrorBody"];
        };
        /**
         * EvidenceStatus
         * @enum {string}
         */
        EvidenceStatus: "audio_and_metadata" | "metadata_only" | "audio_only";
        /** FeedbackEventRecord */
        FeedbackEventRecord: {
            /** Attribute */
            attribute: string | null;
            /** Event Id */
            event_id: string;
            event_type: components["schemas"]["FeedbackType"];
            /** Free Text */
            free_text: string | null;
            /** Query Id */
            query_id: string;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** Track Id */
            track_id: string | null;
            /** Value */
            value: boolean | number | string | null;
        };
        /** FeedbackRequest */
        FeedbackRequest: {
            /** Attribute */
            attribute?: string | null;
            /** @description Typed event; omit to send free_text only. */
            event_type?: components["schemas"]["FeedbackType"] | null;
            /** Free Text */
            free_text?: string | null;
            /**
             * Limit
             * @default 10
             */
            limit?: number;
            /** Query Id */
            query_id: string;
            /**
             * Refresh
             * @description Return the refreshed plate.
             * @default false
             */
            refresh?: boolean;
            /** Session Id */
            session_id: string;
            /** Track Id */
            track_id?: string | null;
            /** Value */
            value?: boolean | number | string | null;
        };
        /**
         * FeedbackResponse
         * @example {
         *       "accepted": true,
         *       "change_summary": [
         *         "excluded trk_example_1",
         *         "added electronic"
         *       ],
         *       "next_action": "REFINE_SEARCH",
         *       "refreshed": {
         *         "capabilities": {
         *           "llm_interpreter": "disabled",
         *           "map": "available",
         *           "semantic": "available"
         *         },
         *         "change_summary": [
         *           "excluded trk_example_1",
         *           "added electronic"
         *         ],
         *         "interpreted_query": {
         *           "diversity": 0.5,
         *           "energy_preferences": [],
         *           "era_preferences": [],
         *           "excluded_track_ids": [
         *             "trk_example_1"
         *           ],
         *           "genre_preferences": [
         *             {
         *               "value": "electronic",
         *               "weight": 0.6
         *             }
         *           ],
         *           "hard_constraints": [],
         *           "instrument_preferences": [
         *             {
         *               "source_span": "flute",
         *               "value": "flute",
         *               "weight": 1
         *             }
         *           ],
         *           "interpreter": "deterministic",
         *           "mood_preferences": [
         *             {
         *               "source_span": "chill",
         *               "value": "chill",
         *               "weight": 0.7
         *             }
         *           ],
         *           "negative_preferences": [],
         *           "negative_reference_track_ids": [],
         *           "original_query": "Something chill with a flute",
         *           "reference_track_ids": [],
         *           "semantic_prompts": [
         *             "chill music featuring flute"
         *           ],
         *           "spec_version": 2,
         *           "tempo_preferences": [],
         *           "texture_preferences": [],
         *           "uncertainties": [],
         *           "vocal_preferences": "unspecified"
         *         },
         *         "no_match_reasons": [],
         *         "outcome": "ok",
         *         "query_id": "qry_example_2",
         *         "results": [
         *           {
         *             "artists": [
         *               {
         *                 "artist_id": "art_example_1",
         *                 "name": "Example Artist 1"
         *               }
         *             ],
         *             "audio_available": true,
         *             "constraint_status": [],
         *             "description": "Its audio is a strong match for “chill music featuring flute”. Tagged Folk.",
         *             "evidence_status": "audio_and_metadata",
         *             "genres": [
         *               "Folk"
         *             ],
         *             "match_reasons": [
         *               "Strong audio match",
         *               "Genre tag: Folk"
         *             ],
         *             "match_strength": "strong",
         *             "preview_url": "/api/tracks/trk_example_1/audio",
         *             "rank": 1,
         *             "retrieval_sources": [
         *               "semantic",
         *               "metadata"
         *             ],
         *             "score": 0.82,
         *             "score_bands": {
         *               "metadata": "partial",
         *               "semantic": "strong"
         *             },
         *             "score_breakdown": {
         *               "final": 0.82,
         *               "metadata": 0.65,
         *               "semantic": 0.82
         *             },
         *             "spatial": {
         *               "projection_version": "umap-example",
         *               "x": -0.5,
         *               "y": 0.25
         *             },
         *             "styles": [],
         *             "title": "Example Track 1",
         *             "track_id": "trk_example_1",
         *             "uncertainty_flags": []
         *           },
         *           {
         *             "artists": [
         *               {
         *                 "artist_id": "art_example_2",
         *                 "name": "Example Artist 2"
         *               }
         *             ],
         *             "audio_available": true,
         *             "constraint_status": [],
         *             "description": "Its audio is a partial match for the requested sound. Tagged Folk.",
         *             "evidence_status": "audio_and_metadata",
         *             "genres": [
         *               "Folk"
         *             ],
         *             "match_reasons": [
         *               "Partial audio match",
         *               "Genre tag: Folk"
         *             ],
         *             "match_strength": "partial",
         *             "preview_url": "/api/tracks/trk_example_2/audio",
         *             "rank": 2,
         *             "retrieval_sources": [
         *               "semantic",
         *               "metadata"
         *             ],
         *             "score": 0.74,
         *             "score_bands": {
         *               "metadata": "partial",
         *               "semantic": "partial"
         *             },
         *             "score_breakdown": {
         *               "final": 0.74,
         *               "metadata": 0.55,
         *               "semantic": 0.74
         *             },
         *             "spatial": {
         *               "projection_version": "umap-example",
         *               "x": -0.4,
         *               "y": 0.25
         *             },
         *             "styles": [],
         *             "title": "Example Track 2",
         *             "track_id": "trk_example_2",
         *             "uncertainty_flags": []
         *           }
         *         ],
         *         "session_id": "ses_example_1",
         *         "warnings": []
         *       },
         *       "updated_search_state": {
         *         "interpreted_query": {
         *           "diversity": 0.5,
         *           "energy_preferences": [],
         *           "era_preferences": [],
         *           "excluded_track_ids": [
         *             "trk_example_1"
         *           ],
         *           "genre_preferences": [
         *             {
         *               "value": "electronic",
         *               "weight": 0.6
         *             }
         *           ],
         *           "hard_constraints": [],
         *           "instrument_preferences": [
         *             {
         *               "source_span": "flute",
         *               "value": "flute",
         *               "weight": 1
         *             }
         *           ],
         *           "interpreter": "deterministic",
         *           "mood_preferences": [
         *             {
         *               "source_span": "chill",
         *               "value": "chill",
         *               "weight": 0.7
         *             }
         *           ],
         *           "negative_preferences": [],
         *           "negative_reference_track_ids": [],
         *           "original_query": "Something chill with a flute",
         *           "reference_track_ids": [],
         *           "semantic_prompts": [
         *             "chill music featuring flute"
         *           ],
         *           "spec_version": 2,
         *           "tempo_preferences": [],
         *           "texture_preferences": [],
         *           "uncertainties": [],
         *           "vocal_preferences": "unspecified"
         *         },
         *         "session_id": "ses_example_1",
         *         "session_version": 4
         *       }
         *     }
         * @example {
         *       "accepted": false,
         *       "change_summary": [],
         *       "next_action": "NONE",
         *       "reason": "nothing in the feedback text maps to a known attribute",
         *       "updated_search_state": {
         *         "interpreted_query": {
         *           "diversity": 0.5,
         *           "energy_preferences": [],
         *           "era_preferences": [],
         *           "excluded_track_ids": [],
         *           "genre_preferences": [],
         *           "hard_constraints": [],
         *           "instrument_preferences": [
         *             {
         *               "source_span": "flute",
         *               "value": "flute",
         *               "weight": 1
         *             }
         *           ],
         *           "interpreter": "deterministic",
         *           "mood_preferences": [
         *             {
         *               "source_span": "chill",
         *               "value": "chill",
         *               "weight": 0.7
         *             }
         *           ],
         *           "negative_preferences": [],
         *           "negative_reference_track_ids": [],
         *           "original_query": "Something chill with a flute",
         *           "reference_track_ids": [],
         *           "semantic_prompts": [
         *             "chill music featuring flute"
         *           ],
         *           "spec_version": 1,
         *           "tempo_preferences": [],
         *           "texture_preferences": [],
         *           "uncertainties": [],
         *           "vocal_preferences": "unspecified"
         *         },
         *         "session_id": "ses_example_1",
         *         "session_version": 2
         *       }
         *     }
         */
        FeedbackResponse: {
            /** Accepted */
            accepted: boolean;
            /** Change Summary */
            change_summary: string[];
            next_action: components["schemas"]["NextAction"];
            /**
             * Reason
             * @description Why the feedback was not applied.
             */
            reason: string | null;
            refreshed: components["schemas"]["SearchResponse"] | null;
            updated_search_state: components["schemas"]["SearchState"];
        };
        /**
         * FeedbackType
         * @description Feedback event types from base.md §8 (wire values are UPPER_SNAKE).
         * @enum {string}
         */
        FeedbackType: "MORE_LIKE_THIS" | "LESS_LIKE_THIS" | "NOT_RELEVANT" | "WRONG_INSTRUMENT" | "MORE_OF_ATTRIBUTE" | "LESS_OF_ATTRIBUTE" | "SELECT_TRACK";
        /** HardConstraint */
        HardConstraint: {
            attribute: components["schemas"]["ConstraintAttribute"];
            operator: components["schemas"]["ConstraintOperator"];
            /** Range */
            range?: [
                number | null,
                number | null
            ] | null;
            /** Value */
            value?: string | null;
        };
        /**
         * HealthResponse
         * @example {
         *       "api_version": "1",
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "status": "ok"
         *     }
         * @example {
         *       "api_version": "1",
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "unavailable",
         *         "semantic": "unavailable"
         *       },
         *       "map_reason": "projection_unavailable",
         *       "semantic_reason": "clap_checkpoint_missing",
         *       "status": "ok"
         *     }
         */
        HealthResponse: {
            /** Api Version */
            api_version: string;
            capabilities: components["schemas"]["Capabilities"];
            /** Map Reason */
            map_reason: string | null;
            /** Semantic Reason */
            semantic_reason: string | null;
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /**
         * InterpretedQuery
         * @description Public view of Agent A's SearchSpecification.
         */
        InterpretedQuery: {
            /** Diversity */
            diversity: number;
            /** Energy Preferences */
            energy_preferences: components["schemas"]["Preference"][];
            /** Era Preferences */
            era_preferences: components["schemas"]["Preference"][];
            /** Excluded Track Ids */
            excluded_track_ids: string[];
            /** Genre Preferences */
            genre_preferences: components["schemas"]["Preference"][];
            /** Hard Constraints */
            hard_constraints: components["schemas"]["HardConstraint"][];
            /** Instrument Preferences */
            instrument_preferences: components["schemas"]["Preference"][];
            /**
             * Interpreter
             * @enum {string}
             */
            interpreter: "deterministic" | "llm";
            /** Interpreter Model */
            interpreter_model: string | null;
            /** Mood Preferences */
            mood_preferences: components["schemas"]["Preference"][];
            /** Negative Preferences */
            negative_preferences: components["schemas"]["Preference"][];
            /** Negative Reference Track Ids */
            negative_reference_track_ids: string[];
            /** Original Query */
            original_query: string;
            /** Reference Track Ids */
            reference_track_ids: string[];
            /** Semantic Prompts */
            semantic_prompts: string[];
            /** Spec Version */
            spec_version: number;
            /** Tempo Preferences */
            tempo_preferences: components["schemas"]["Preference"][];
            /** Texture Preferences */
            texture_preferences: components["schemas"]["Preference"][];
            /** Uncertainties */
            uncertainties: string[];
            /**
             * Vocal Preferences
             * @enum {string}
             */
            vocal_preferences: "required" | "preferred" | "avoided" | "excluded" | "unspecified";
        };
        /**
         * InterpreterStatus
         * @enum {string}
         */
        InterpreterStatus: "used" | "fallback" | "disabled";
        JsonValue: unknown;
        /** MapBounds */
        MapBounds: {
            /** Max X */
            max_x: number;
            /** Max Y */
            max_y: number;
            /** Min X */
            min_x: number;
            /** Min Y */
            min_y: number;
        };
        /**
         * MapMetaResponse
         * @example {
         *       "bounds": {
         *         "max_x": 1,
         *         "max_y": 0.9,
         *         "min_x": -1,
         *         "min_y": -0.9
         *       },
         *       "coordinate_transform": {
         *         "center": [
         *           0,
         *           0
         *         ],
         *         "kind": "center_scale",
         *         "scale": 1
         *       },
         *       "created_at": "2026-01-01T12:00:00Z",
         *       "embedding_version": "ev-example",
         *       "excluded_tracks": 1,
         *       "model_id": "example-clap-model",
         *       "n_points": 5,
         *       "projection_version": "umap-example",
         *       "status": "available"
         *     }
         * @example {
         *       "n_points": 0,
         *       "reason": "projection_unavailable",
         *       "status": "unavailable"
         *     }
         */
        MapMetaResponse: {
            bounds: components["schemas"]["MapBounds"] | null;
            /** Coordinate Transform */
            coordinate_transform: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /** Created At */
            created_at: string | null;
            /** Embedding Version */
            embedding_version: string | null;
            /**
             * Excluded Tracks
             * @description Catalog tracks without audio, not shown.
             */
            excluded_tracks: number | null;
            /** Model Id */
            model_id: string | null;
            /** N Points */
            n_points: number;
            /** Projection Version */
            projection_version: string | null;
            /** Reason */
            reason: string | null;
            status: components["schemas"]["CapabilityStatus"];
        };
        /** MapPoint */
        MapPoint: {
            /** Artist */
            artist: string | null;
            /** Genre */
            genre: string | null;
            /** Has Audio */
            has_audio: boolean;
            /** Source Url */
            source_url: string | null;
            /** Style */
            style: string | null;
            /** Title */
            title: string;
            /** Track Id */
            track_id: string;
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /**
         * MapPointsResponse
         * @example {
         *       "next_cursor": "trk_example_3",
         *       "points": [
         *         {
         *           "artist": "Example Artist 1",
         *           "genre": "Folk",
         *           "has_audio": true,
         *           "title": "Example Track 1",
         *           "track_id": "trk_example_1",
         *           "x": -0.6,
         *           "y": 0.3
         *         },
         *         {
         *           "artist": "Example Artist 2",
         *           "genre": "Electronic",
         *           "has_audio": true,
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2",
         *           "x": -0.2,
         *           "y": 0
         *         },
         *         {
         *           "artist": "Example Artist 3",
         *           "genre": "Folk",
         *           "has_audio": true,
         *           "title": "Example Track 3",
         *           "track_id": "trk_example_3",
         *           "x": 0.2,
         *           "y": -0.3
         *         }
         *       ],
         *       "projection_version": "umap-example"
         *     }
         * @example {
         *       "points": [
         *         {
         *           "artist": "Example Artist 4",
         *           "genre": "Electronic",
         *           "has_audio": true,
         *           "title": "Example Track 4",
         *           "track_id": "trk_example_4",
         *           "x": 0.6,
         *           "y": -0.6
         *         },
         *         {
         *           "artist": "Example Artist 5",
         *           "genre": "Folk",
         *           "has_audio": true,
         *           "title": "Example Track 5",
         *           "track_id": "trk_example_5",
         *           "x": 1,
         *           "y": -0.9
         *         }
         *       ],
         *       "projection_version": "umap-example"
         *     }
         */
        MapPointsResponse: {
            /**
             * Next Cursor
             * @description Pass as `cursor` for the next page.
             */
            next_cursor: string | null;
            /** Points */
            points: components["schemas"]["MapPoint"][];
            /** Projection Version */
            projection_version: string;
        };
        /**
         * MatchStrength
         * @enum {string}
         */
        MatchStrength: "strong" | "partial" | "weak";
        /** Neighbor */
        Neighbor: {
            /** Artists */
            artists: components["schemas"]["Artist"][];
            /** Audio Available */
            audio_available: boolean;
            /** Relationship Types */
            relationship_types: components["schemas"]["RelationshipType"][];
            /**
             * Score
             * @description Cosine for clap_cosine; the relationship weight (often null) otherwise.
             */
            score: number | null;
            spatial: components["schemas"]["Spatial"] | null;
            /** Title */
            title: string;
            /** Track Id */
            track_id: string;
        };
        /**
         * NeighborsResponse
         * @example {
         *       "metric": "clap_cosine",
         *       "model_id": "example-clap-model",
         *       "neighbors": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_2",
         *               "name": "Example Artist 2"
         *             }
         *           ],
         *           "audio_available": true,
         *           "relationship_types": [],
         *           "score": 0.85,
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.4,
         *             "y": 0.3
         *           },
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2"
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_4",
         *               "name": "Example Artist 4"
         *             }
         *           ],
         *           "audio_available": true,
         *           "relationship_types": [],
         *           "score": 0.75,
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.3,
         *             "y": 0.3
         *           },
         *           "title": "Example Track 4",
         *           "track_id": "trk_example_4"
         *         }
         *       ],
         *       "track_id": "trk_example_1"
         *     }
         * @example {
         *       "metric": "catalog_relationship",
         *       "neighbors": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_3",
         *               "name": "Example Artist 3"
         *             }
         *           ],
         *           "audio_available": false,
         *           "relationship_types": [
         *             "same_artist"
         *           ],
         *           "title": "Example Track 5",
         *           "track_id": "trk_example_5"
         *         }
         *       ],
         *       "reason": "no_audio_embedding",
         *       "track_id": "trk_example_3"
         *     }
         */
        NeighborsResponse: {
            /**
             * Metric
             * @enum {string}
             */
            metric: "clap_cosine" | "catalog_relationship";
            /** Model Id */
            model_id: string | null;
            /** Neighbors */
            neighbors: components["schemas"]["Neighbor"][];
            /**
             * Reason
             * @description Why audio neighbors are missing; null for clap_cosine.
             */
            reason: ("no_audio_embedding" | "semantic_unavailable") | null;
            /** Track Id */
            track_id: string;
        };
        /**
         * NextAction
         * @enum {string}
         */
        NextAction: "REFINE_SEARCH" | "SHOW_DETAILS" | "NONE";
        /** Preference */
        Preference: {
            /** Source Span */
            source_span?: string | null;
            /** Value */
            value: string;
            /** Weight */
            weight: number;
        };
        /** RelatedTrack */
        RelatedTrack: {
            /** Artists */
            artists: components["schemas"]["Artist"][];
            relationship_type: components["schemas"]["RelationshipType"];
            /** Title */
            title: string;
            /** Track Id */
            track_id: string;
        };
        /**
         * RelationshipType
         * @enum {string}
         */
        RelationshipType: "same_artist" | "same_label" | "same_master" | "same_release" | "shared_style";
        /** Release */
        Release: {
            /** Release Id */
            release_id: string;
            /** Title */
            title: string;
            /** Year */
            year: number | null;
        };
        /**
         * RetrievalSource
         * @enum {string}
         */
        RetrievalSource: "metadata" | "semantic" | "relationship";
        /**
         * ScoreBands
         * @description Strength band per signal within this query; `null` = the signal is missing for this track
         *     (or has no calibrated bands). Show these, never the numbers.
         */
        ScoreBands: {
            metadata: components["schemas"]["MatchStrength"] | null;
            relationship: components["schemas"]["MatchStrength"] | null;
            semantic: components["schemas"]["MatchStrength"] | null;
        };
        /**
         * ScoreBreakdown
         * @description Normalized signals; `null` means the signal was not computed for this track.
         */
        ScoreBreakdown: {
            /** Final */
            final: number;
            /** Metadata */
            metadata: number | null;
            /** Relationship */
            relationship: number | null;
            /** Semantic */
            semantic: number | null;
        };
        /**
         * SearchOutcomeKind
         * @enum {string}
         */
        SearchOutcomeKind: "ok" | "no_confident_match" | "needs_clarification";
        /** SearchRequest */
        SearchRequest: {
            /**
             * Limit
             * @default 10
             */
            limit?: number;
            /** Query */
            query: string;
            /**
             * Session Id
             * @description Continue an existing session (follow-up query).
             */
            session_id?: string | null;
        };
        /**
         * SearchResponse
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "Something chill with a flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "ok",
         *       "query_id": "qry_example_1",
         *       "results": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_1",
         *               "name": "Example Artist 1"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Its audio is a strong match for “chill music featuring flute”. Tagged Folk.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Strong audio match",
         *             "Genre tag: Folk"
         *           ],
         *           "match_strength": "strong",
         *           "preview_url": "/api/tracks/trk_example_1/audio",
         *           "rank": 1,
         *           "retrieval_sources": [
         *             "semantic",
         *             "metadata"
         *           ],
         *           "score": 0.82,
         *           "score_bands": {
         *             "metadata": "partial",
         *             "semantic": "strong"
         *           },
         *           "score_breakdown": {
         *             "final": 0.82,
         *             "metadata": 0.65,
         *             "semantic": 0.82
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.5,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 1",
         *           "track_id": "trk_example_1",
         *           "uncertainty_flags": []
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_2",
         *               "name": "Example Artist 2"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Its audio is a partial match for the requested sound. Tagged Folk.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Partial audio match",
         *             "Genre tag: Folk"
         *           ],
         *           "match_strength": "partial",
         *           "preview_url": "/api/tracks/trk_example_2/audio",
         *           "rank": 2,
         *           "retrieval_sources": [
         *             "semantic",
         *             "metadata"
         *           ],
         *           "score": 0.74,
         *           "score_bands": {
         *             "metadata": "partial",
         *             "semantic": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.74,
         *             "metadata": 0.55,
         *             "semantic": 0.74
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.4,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2",
         *           "uncertainty_flags": []
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_3",
         *               "name": "Example Artist 3"
         *             }
         *           ],
         *           "audio_available": false,
         *           "constraint_status": [],
         *           "description": "Matched on metadata: Tagged Folk. Audio analysis unavailable.",
         *           "evidence_status": "metadata_only",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Genre tag: Folk"
         *           ],
         *           "rank": 3,
         *           "retrieval_sources": [
         *             "metadata"
         *           ],
         *           "score": 0.05,
         *           "score_bands": {
         *             "metadata": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.05,
         *             "metadata": 0.3
         *           },
         *           "styles": [],
         *           "title": "Example Track 3",
         *           "track_id": "trk_example_3",
         *           "uncertainty_flags": [
         *             "no_audio"
         *           ]
         *         }
         *       ],
         *       "session_id": "ses_example_1",
         *       "warnings": []
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "Something chill with a flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "ok",
         *       "query_id": "qry_example_1",
         *       "results": [],
         *       "session_id": "ses_example_1",
         *       "warnings": []
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [
         *           {
         *             "attribute": "vocals",
         *             "operator": "excluded"
         *           }
         *         ],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "instrumental only flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "excluded"
         *       },
         *       "no_match_reasons": [
         *         "no track has reliable evidence for: vocals excluded"
         *       ],
         *       "outcome": "no_confident_match",
         *       "query_id": "qry_example_1",
         *       "results": [],
         *       "session_id": "ses_example_1",
         *       "warnings": []
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "clarification_question": "Should the music have vocals or not?",
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "no vocals with female vocals",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [
         *           "vocals are both excluded and requested"
         *         ],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "needs_clarification",
         *       "query_id": "qry_example_1",
         *       "results": [],
         *       "session_id": "ses_example_1",
         *       "warnings": []
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "unavailable"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "Something chill with a flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "ok",
         *       "query_id": "qry_example_1",
         *       "results": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_1",
         *               "name": "Example Artist 1"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Matched on metadata: Tagged Folk. Audio analysis unavailable.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Genre tag: Folk"
         *           ],
         *           "preview_url": "/api/tracks/trk_example_1/audio",
         *           "rank": 1,
         *           "retrieval_sources": [
         *             "metadata"
         *           ],
         *           "score": 0.65,
         *           "score_bands": {
         *             "metadata": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.65,
         *             "metadata": 0.65
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.5,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 1",
         *           "track_id": "trk_example_1",
         *           "uncertainty_flags": []
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_2",
         *               "name": "Example Artist 2"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Matched on metadata: Tagged Folk. Audio analysis unavailable.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Genre tag: Folk"
         *           ],
         *           "preview_url": "/api/tracks/trk_example_2/audio",
         *           "rank": 2,
         *           "retrieval_sources": [
         *             "metadata"
         *           ],
         *           "score": 0.55,
         *           "score_bands": {
         *             "metadata": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.55,
         *             "metadata": 0.55
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.4,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2",
         *           "uncertainty_flags": []
         *         }
         *       ],
         *       "session_id": "ses_example_1",
         *       "warnings": [
         *         {
         *           "code": "semantic_unavailable",
         *           "message": "Audio-semantic search is unavailable; results are ranked on metadata only."
         *         }
         *       ]
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "fallback",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "Something chill with a flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "ok",
         *       "query_id": "qry_example_1",
         *       "results": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_1",
         *               "name": "Example Artist 1"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Its audio is a strong match for “chill music featuring flute”. Tagged Folk.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Strong audio match",
         *             "Genre tag: Folk"
         *           ],
         *           "match_strength": "strong",
         *           "preview_url": "/api/tracks/trk_example_1/audio",
         *           "rank": 1,
         *           "retrieval_sources": [
         *             "semantic",
         *             "metadata"
         *           ],
         *           "score": 0.82,
         *           "score_bands": {
         *             "metadata": "partial",
         *             "semantic": "strong"
         *           },
         *           "score_breakdown": {
         *             "final": 0.82,
         *             "metadata": 0.65,
         *             "semantic": 0.82
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.5,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 1",
         *           "track_id": "trk_example_1",
         *           "uncertainty_flags": []
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_2",
         *               "name": "Example Artist 2"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [],
         *           "description": "Its audio is a partial match for the requested sound. Tagged Folk.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Partial audio match",
         *             "Genre tag: Folk"
         *           ],
         *           "match_strength": "partial",
         *           "preview_url": "/api/tracks/trk_example_2/audio",
         *           "rank": 2,
         *           "retrieval_sources": [
         *             "semantic",
         *             "metadata"
         *           ],
         *           "score": 0.74,
         *           "score_bands": {
         *             "metadata": "partial",
         *             "semantic": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.74,
         *             "metadata": 0.55,
         *             "semantic": 0.74
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.4,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2",
         *           "uncertainty_flags": []
         *         },
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_3",
         *               "name": "Example Artist 3"
         *             }
         *           ],
         *           "audio_available": false,
         *           "constraint_status": [],
         *           "description": "Matched on metadata: Tagged Folk. Audio analysis unavailable.",
         *           "evidence_status": "metadata_only",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Genre tag: Folk"
         *           ],
         *           "rank": 3,
         *           "retrieval_sources": [
         *             "metadata"
         *           ],
         *           "score": 0.05,
         *           "score_bands": {
         *             "metadata": "partial"
         *           },
         *           "score_breakdown": {
         *             "final": 0.05,
         *             "metadata": 0.3
         *           },
         *           "styles": [],
         *           "title": "Example Track 3",
         *           "track_id": "trk_example_3",
         *           "uncertainty_flags": [
         *             "no_audio"
         *           ]
         *         }
         *       ],
         *       "session_id": "ses_example_1",
         *       "warnings": [
         *         {
         *           "code": "llm_fallback",
         *           "message": "The language model did not answer; the query was read by the deterministic parser."
         *         }
         *       ]
         *     }
         * @example {
         *       "capabilities": {
         *         "llm_interpreter": "disabled",
         *         "map": "available",
         *         "semantic": "available"
         *       },
         *       "change_summary": [],
         *       "interpreted_query": {
         *         "diversity": 0.5,
         *         "energy_preferences": [],
         *         "era_preferences": [],
         *         "excluded_track_ids": [],
         *         "genre_preferences": [],
         *         "hard_constraints": [],
         *         "instrument_preferences": [
         *           {
         *             "source_span": "flute",
         *             "value": "flute",
         *             "weight": 1
         *           }
         *         ],
         *         "interpreter": "deterministic",
         *         "mood_preferences": [
         *           {
         *             "source_span": "chill",
         *             "value": "chill",
         *             "weight": 0.7
         *           }
         *         ],
         *         "negative_preferences": [],
         *         "negative_reference_track_ids": [],
         *         "original_query": "Something chill with a flute",
         *         "reference_track_ids": [],
         *         "semantic_prompts": [
         *           "chill music featuring flute"
         *         ],
         *         "spec_version": 1,
         *         "tempo_preferences": [],
         *         "texture_preferences": [],
         *         "uncertainties": [],
         *         "vocal_preferences": "unspecified"
         *       },
         *       "no_match_reasons": [],
         *       "outcome": "ok",
         *       "query_id": "qry_example_1",
         *       "results": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_1",
         *               "name": "Example Artist 1"
         *             }
         *           ],
         *           "audio_available": true,
         *           "constraint_status": [
         *             {
         *               "attribute": "vocals",
         *               "operator": "excluded",
         *               "status": "unknown"
         *             }
         *           ],
         *           "description": "Its audio is a strong match for “chill music featuring flute”. Tagged Folk.",
         *           "evidence_status": "audio_and_metadata",
         *           "genres": [
         *             "Folk"
         *           ],
         *           "match_reasons": [
         *             "Strong audio match",
         *             "Genre tag: Folk"
         *           ],
         *           "match_strength": "strong",
         *           "preview_url": "/api/tracks/trk_example_1/audio",
         *           "rank": 1,
         *           "retrieval_sources": [
         *             "semantic",
         *             "metadata"
         *           ],
         *           "score": 0.82,
         *           "score_bands": {
         *             "metadata": "partial",
         *             "semantic": "strong"
         *           },
         *           "score_breakdown": {
         *             "final": 0.82,
         *             "metadata": 0.65,
         *             "semantic": 0.82
         *           },
         *           "spatial": {
         *             "projection_version": "umap-example",
         *             "x": -0.5,
         *             "y": 0.25
         *           },
         *           "styles": [],
         *           "title": "Example Track 1",
         *           "track_id": "trk_example_1",
         *           "uncertainty_flags": [
         *             "vocals_unknown"
         *           ]
         *         }
         *       ],
         *       "session_id": "ses_example_1",
         *       "warnings": []
         *     }
         */
        SearchResponse: {
            capabilities: components["schemas"]["Capabilities"];
            /**
             * Change Summary
             * @description What changed since the previous turn.
             */
            change_summary: string[];
            /** Clarification Question */
            clarification_question: string | null;
            interpreted_query: components["schemas"]["InterpretedQuery"];
            /**
             * No Match Reasons
             * @description Why nothing was confident (outcome no_confident_match).
             */
            no_match_reasons: string[];
            outcome: components["schemas"]["SearchOutcomeKind"];
            /**
             * Query Id
             * @description Null only when no search ran.
             */
            query_id: string | null;
            /** Results */
            results: components["schemas"]["TrackResult"][];
            /** Session Id */
            session_id: string;
            /** Warnings */
            warnings: components["schemas"]["ApiWarning"][];
        };
        /** SearchState */
        SearchState: {
            interpreted_query: components["schemas"]["InterpretedQuery"];
            /** Session Id */
            session_id: string;
            /** Session Version */
            session_version: number;
        };
        /**
         * SessionResponse
         * @example {
         *       "created_at": "2026-01-01T12:00:00Z",
         *       "feedback": [
         *         {
         *           "event_id": "evt_example_1",
         *           "event_type": "NOT_RELEVANT",
         *           "query_id": "qry_example_1",
         *           "timestamp": "2026-01-01T12:00:00Z",
         *           "track_id": "trk_example_1"
         *         }
         *       ],
         *       "original_query": "Something chill with a flute",
         *       "session_id": "ses_example_1",
         *       "turns": [
         *         {
         *           "change_summary": [],
         *           "created_at": "2026-01-01T12:00:00Z",
         *           "interpreted_query": {
         *             "diversity": 0.5,
         *             "energy_preferences": [],
         *             "era_preferences": [],
         *             "excluded_track_ids": [],
         *             "genre_preferences": [],
         *             "hard_constraints": [],
         *             "instrument_preferences": [
         *               {
         *                 "source_span": "flute",
         *                 "value": "flute",
         *                 "weight": 1
         *               }
         *             ],
         *             "interpreter": "deterministic",
         *             "mood_preferences": [
         *               {
         *                 "source_span": "chill",
         *                 "value": "chill",
         *                 "weight": 0.7
         *               }
         *             ],
         *             "negative_preferences": [],
         *             "negative_reference_track_ids": [],
         *             "original_query": "Something chill with a flute",
         *             "reference_track_ids": [],
         *             "semantic_prompts": [
         *               "chill music featuring flute"
         *             ],
         *             "spec_version": 1,
         *             "tempo_preferences": [],
         *             "texture_preferences": [],
         *             "uncertainties": [],
         *             "vocal_preferences": "unspecified"
         *           },
         *           "query_id": "qry_example_1",
         *           "query_text": "Something chill with a flute",
         *           "result_track_ids": [
         *             "trk_example_1",
         *             "trk_example_2",
         *             "trk_example_3"
         *           ]
         *         },
         *         {
         *           "change_summary": [
         *             "excluded trk_example_1",
         *             "added electronic"
         *           ],
         *           "created_at": "2026-01-01T12:00:00Z",
         *           "interpreted_query": {
         *             "diversity": 0.5,
         *             "energy_preferences": [],
         *             "era_preferences": [],
         *             "excluded_track_ids": [
         *               "trk_example_1"
         *             ],
         *             "genre_preferences": [
         *               {
         *                 "value": "electronic",
         *                 "weight": 0.6
         *               }
         *             ],
         *             "hard_constraints": [],
         *             "instrument_preferences": [
         *               {
         *                 "source_span": "flute",
         *                 "value": "flute",
         *                 "weight": 1
         *               }
         *             ],
         *             "interpreter": "deterministic",
         *             "mood_preferences": [
         *               {
         *                 "source_span": "chill",
         *                 "value": "chill",
         *                 "weight": 0.7
         *               }
         *             ],
         *             "negative_preferences": [],
         *             "negative_reference_track_ids": [],
         *             "original_query": "Something chill with a flute",
         *             "reference_track_ids": [],
         *             "semantic_prompts": [
         *               "chill music featuring flute"
         *             ],
         *             "spec_version": 2,
         *             "tempo_preferences": [],
         *             "texture_preferences": [],
         *             "uncertainties": [],
         *             "vocal_preferences": "unspecified"
         *           },
         *           "query_id": "qry_example_2",
         *           "query_text": "Something chill with a flute",
         *           "result_track_ids": [
         *             "trk_example_1",
         *             "trk_example_2"
         *           ],
         *           "triggered_by_event_id": "evt_example_1"
         *         }
         *       ],
         *       "version": 4
         *     }
         */
        SessionResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Feedback */
            feedback: components["schemas"]["FeedbackEventRecord"][];
            /** Original Query */
            original_query: string | null;
            /** Session Id */
            session_id: string;
            /** Turns */
            turns: components["schemas"]["SessionTurn"][];
            /** Version */
            version: number;
        };
        /** SessionTurn */
        SessionTurn: {
            /** Change Summary */
            change_summary: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            interpreted_query: components["schemas"]["InterpretedQuery"];
            /** Query Id */
            query_id: string;
            /** Query Text */
            query_text: string;
            /** Result Track Ids */
            result_track_ids: string[];
            /** Triggered By Event Id */
            triggered_by_event_id: string | null;
        };
        /**
         * Spatial
         * @description UMAP visualization coordinates; not a similarity measure.
         */
        Spatial: {
            /** Projection Version */
            projection_version: string;
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /**
         * TrackDetail
         * @example {
         *       "artists": [
         *         {
         *           "artist_id": "art_example_1",
         *           "name": "Example Artist 1"
         *         }
         *       ],
         *       "audio": {
         *         "duration_seconds": 30,
         *         "license": "Example license"
         *       },
         *       "audio_available": true,
         *       "duration_seconds": 212,
         *       "evidence_status": "audio_and_metadata",
         *       "genres": [
         *         "Folk"
         *       ],
         *       "preview_url": "/api/tracks/trk_example_1/audio",
         *       "related_tracks": [
         *         {
         *           "artists": [
         *             {
         *               "artist_id": "art_example_1",
         *               "name": "Example Artist 1"
         *             }
         *           ],
         *           "relationship_type": "same_artist",
         *           "title": "Example Track 2",
         *           "track_id": "trk_example_2"
         *         }
         *       ],
         *       "relationship_counts": {
         *         "same_artist": 1
         *       },
         *       "release": {
         *         "release_id": "rel_example_1",
         *         "title": "Example Album",
         *         "year": 2012
         *       },
         *       "spatial": {
         *         "projection_version": "umap-example",
         *         "x": -0.5,
         *         "y": 0.25
         *       },
         *       "styles": [],
         *       "tags": [
         *         "flute"
         *       ],
         *       "title": "Example Track 1",
         *       "track_id": "trk_example_1",
         *       "year": 2012
         *     }
         * @example {
         *       "artists": [
         *         {
         *           "artist_id": "art_example_3",
         *           "name": "Example Artist 3"
         *         }
         *       ],
         *       "audio_available": false,
         *       "evidence_status": "metadata_only",
         *       "genres": [
         *         "Folk"
         *       ],
         *       "related_tracks": [],
         *       "relationship_counts": {},
         *       "styles": [],
         *       "tags": [],
         *       "title": "Example Track 3",
         *       "track_id": "trk_example_3"
         *     }
         */
        TrackDetail: {
            /** Artists */
            artists: components["schemas"]["Artist"][];
            /** @description The validated local clip, when there is one. */
            audio: components["schemas"]["AudioInfo"] | null;
            /** Audio Available */
            audio_available: boolean;
            /** Duration Seconds */
            duration_seconds: number | null;
            evidence_status: components["schemas"]["EvidenceStatus"];
            /** Genres */
            genres: string[];
            /** Preview Url */
            preview_url: string | null;
            /**
             * Related Tracks
             * @description Catalog context (not audio similarity); capped per relationship type.
             */
            related_tracks: components["schemas"]["RelatedTrack"][];
            /** Relationship Counts */
            relationship_counts: {
                [key: string]: number;
            };
            release: components["schemas"]["Release"] | null;
            /** Source Url */
            source_url: string | null;
            spatial: components["schemas"]["Spatial"] | null;
            /** Styles */
            styles: string[];
            /** Tags */
            tags: string[];
            /** Title */
            title: string;
            /** Track Id */
            track_id: string;
            /** Year */
            year: number | null;
        };
        /** TrackResult */
        TrackResult: {
            /** Artists */
            artists: components["schemas"]["Artist"][];
            /**
             * Audio Available
             * @description An audio embedding exists (audio was analyzed).
             */
            audio_available: boolean;
            /** Constraint Status */
            constraint_status: components["schemas"]["ConstraintCheck"][];
            /**
             * Description
             * @description Evidence-grounded text; null when too thin.
             */
            description: string | null;
            evidence_status: components["schemas"]["EvidenceStatus"];
            /** Genres */
            genres: string[];
            /** Match Reasons */
            match_reasons: string[];
            /** @description Band of the audio (CLAP) match within this query, the one match_reasons describe; null when the track has no semantic score. */
            match_strength: components["schemas"]["MatchStrength"] | null;
            /** Preview Url */
            preview_url: string | null;
            /** Rank */
            rank: number;
            /** Retrieval Sources */
            retrieval_sources: components["schemas"]["RetrievalSource"][];
            /**
             * Score
             * @description Relevance for ordering; not a probability.
             */
            score: number;
            score_bands: components["schemas"]["ScoreBands"];
            score_breakdown: components["schemas"]["ScoreBreakdown"];
            /** Source Url */
            source_url: string | null;
            spatial: components["schemas"]["Spatial"] | null;
            /** Styles */
            styles: string[];
            /** Title */
            title: string;
            /** Track Id */
            track_id: string;
            /** Uncertainty Flags */
            uncertainty_flags: string[];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    submitFeedback: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackResponse"];
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflicts with the session state. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMapMeta: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MapMetaResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMapPoints: {
        parameters: {
            query?: {
                artist_id?: string | null;
                /** @description `next_cursor` of the previous page. */
                cursor?: string | null;
                genre?: string | null;
                has_audio?: boolean | null;
                limit?: number;
                style?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MapPointsResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description A required capability is unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    search: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResponse"];
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSession: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getTrack: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                track_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TrackDetail"];
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getTrackAudio: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                track_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The audio clip. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "audio/mpeg": unknown;
                };
            };
            /** @description Requested byte range. */
            206: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "audio/mpeg": unknown;
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getTrackNeighbors: {
        parameters: {
            query?: {
                /** @description Number of neighbors. */
                k?: number;
            };
            header?: never;
            path: {
                track_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NeighborsResponse"];
                };
            };
            /** @description Not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unexpected error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
