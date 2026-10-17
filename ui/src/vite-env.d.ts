
interface ImportMetaEnv {
  /** The commit this build came from (the image's PW_COMMIT); empty locally. */
  readonly VITE_PW_COMMIT?: string;
}
